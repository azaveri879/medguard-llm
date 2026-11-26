# Gateway image with the PHI model baked in, used when enableNer=true.
# The gateway runs in isolated subnets, so the model cannot be downloaded at runtime.
# Python 3.12 because the 3.11 base image's glibc is too old for current torch wheels.
#
# By default the image bakes in obi/deid_roberta_i2b2 from the Hugging Face Hub.
# To bake in a local model directory instead (for example a retrained one), pass it
# as the "model" build context:
#   docker build --build-context model=../../eval/models/seed11 -t medguard-gateway .
# Models retrained on MIMIC must not be pushed to any registry.

# Empty unless --build-context model=DIR overrides it.
FROM scratch AS model

FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt requirements-ner.txt /tmp/build/
RUN pip install --no-cache-dir torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r /tmp/build/requirements.txt -r /tmp/build/requirements-ner.txt

# Hub model to bake in when no local model is given. HF_WEIGHTS_REVISION is for
# repos whose safetensors file lives on a different commit than the config, such
# as StanfordAIMI/stanford-deidentifier-base, whose model.safetensors is only on
# the Hub's safetensors-conversion pull request (refs/pr/5).
ARG HF_MODEL=obi/deid_roberta_i2b2
ARG HF_REVISION=78f2152eb93ddd817290ce8dbe46f1a6685e09fc
ARG HF_WEIGHTS_REVISION=

COPY --from=model / /opt/model/
RUN if [ -f /opt/model/model.safetensors ]; then \
      echo "Using the local model from the build context"; \
    else \
      python -c "import sys; from huggingface_hub import hf_hub_download, snapshot_download; \
model, rev, weights_rev = sys.argv[1], sys.argv[2], sys.argv[3] or sys.argv[2]; \
snapshot_download(model, revision=rev, allow_patterns=['*.json', '*.txt', 'merges*', 'vocab*'], local_dir='/opt/model'); \
hf_hub_download(model, 'model.safetensors', revision=weights_rev, local_dir='/opt/model')" \
        "$HF_MODEL" "$HF_REVISION" "$HF_WEIGHTS_REVISION"; \
    fi

ENV PHI_NER_MODEL=/opt/model
ENV HF_HOME=/tmp/hf
ENV HF_HUB_OFFLINE=1

COPY handler.py phi_redaction.py ner_redaction.py known_names.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]

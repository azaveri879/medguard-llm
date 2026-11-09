# Gateway image with the PHI model baked in, used when enableNer=true.
# The gateway runs in isolated subnets, so the model cannot be downloaded at runtime.
FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt requirements-ner.txt /tmp/build/
RUN pip install --no-cache-dir torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r /tmp/build/requirements.txt -r /tmp/build/requirements-ner.txt

RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('obi/deid_roberta_i2b2', revision='78f2152eb93ddd817290ce8dbe46f1a6685e09fc', allow_patterns=['*.json', '*.txt', 'merges*', 'vocab*', 'model.safetensors'], local_dir='/opt/model')"

ENV PHI_NER_MODEL=/opt/model
ENV HF_HOME=/tmp/hf
ENV HF_HUB_OFFLINE=1

COPY handler.py phi_redaction.py ner_redaction.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]

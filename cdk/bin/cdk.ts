#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { MedGuardStack } from "../lib/medguard-stack";

const app = new cdk.App();

new MedGuardStack(app, "MedGuardStack", {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});


import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as apigw from "aws-cdk-lib/aws-apigateway";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as path from "path";

export class MedGuardStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ---------- Config ----------
    const bedrockModelId =
      this.node.tryGetContext("bedrockModelId") ??
      "anthropic.claude-3-haiku-20240307-v1:0"; // Base model ID
    const enableAuth =
      this.node.tryGetContext("enableAuth") !== "false"; // Default: true, set to "false" to disable

    // ---------- VPC ----------
    const vpc = new ec2.Vpc(this, "MedGuardVpc", {
      maxAzs: 2,
      natGateways: 0, // No NAT - using VPC endpoints for all AWS services
      subnetConfiguration: [
        {
          name: "private",
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED, // Isolated subnets - no internet egress
        },
      ],
    });

    // VPC Gateway endpoints for S3/DynamoDB (lets Lambda talk to them without NAT)
    vpc.addGatewayEndpoint("S3Endpoint", {
      service: ec2.GatewayVpcEndpointAwsService.S3,
    });

    vpc.addGatewayEndpoint("DynamoEndpoint", {
      service: ec2.GatewayVpcEndpointAwsService.DYNAMODB,
    });

    // Bedrock Runtime VPC Interface Endpoint (PrivateLink)
    // This allows Lambda to access Bedrock without internet/NAT gateway
    vpc.addInterfaceEndpoint("BedrockRuntimeEndpoint", {
      service: ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME,
      // Place endpoint in isolated subnets
      subnets: {
        subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
      },
    });

    // ---------- Storage ----------
    const auditBucket = new s3.Bucket(this, "AuditBucket", {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      versioned: true,
      lifecycleRules: [{ expiration: cdk.Duration.days(365) }],
      // Object Lock (WORM) requires bucket-level property at creation AND some account settings.
      // Enable later once you confirm org requirements:
      // objectLockEnabled: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const auditTable = new dynamodb.Table(this, "AuditTable", {
      partitionKey: { name: "request_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "ts", type: dynamodb.AttributeType.NUMBER },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ---------- Lambda ----------
    const logGroup = new logs.LogGroup(this, "GatewayFnLogGroup", {
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const gatewayFn = new lambda.Function(this, "GatewayFn", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../../services/gateway")),
      memorySize: 1024,
      timeout: cdk.Duration.seconds(30),
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      environment: {
        AUDIT_BUCKET: auditBucket.bucketName,
        AUDIT_PREFIX: "events/",
        DDB_TABLE: auditTable.tableName,
        BEDROCK_MODEL_ID: bedrockModelId,
      },
      logGroup,
    });

    // IAM perms for S3 + DDB + Bedrock
    auditBucket.grantPut(gatewayFn);
    auditTable.grantWriteData(gatewayFn);

    // Bedrock invoke permission (scope to the model if you want stricter control later)
    gatewayFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        resources: ["*"],
      })
    );

    // AWS Marketplace permissions (required for some Bedrock models)
    gatewayFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe",
        ],
        resources: ["*"],
      })
    );

    // ---------- Cognito User Pool (Authentication) ----------
    // Only create if authentication is enabled
    let userPool: cognito.UserPool | undefined;
    let userPoolClient: cognito.UserPoolClient | undefined;

    if (enableAuth) {
      userPool = new cognito.UserPool(this, "MedGuardUserPool", {
        userPoolName: "medguard-users",
        selfSignUpEnabled: false, // Admin creates users only
        signInAliases: {
          email: true,
        },
        autoVerify: {
          email: true,
        },
        standardAttributes: {
          email: {
            required: true,
            mutable: true,
          },
        },
        passwordPolicy: {
          minLength: 12,
          requireLowercase: true,
          requireUppercase: true,
          requireDigits: true,
          requireSymbols: true,
        },
        removalPolicy: cdk.RemovalPolicy.RETAIN,
      });

      // User Pool Client for API access
      userPoolClient = new cognito.UserPoolClient(this, "MedGuardUserPoolClient", {
        userPool,
        userPoolClientName: "medguard-api-client",
        generateSecret: false, // Public client for API Gateway
        authFlows: {
          userPassword: true,
          userSrp: true,
        },
      });
    }

    // ---------- API Gateway ----------
    // Create CloudWatch Logs role for API Gateway (required for logging)
    const apiGatewayLogRole = new iam.Role(this, "ApiGatewayLogRole", {
      assumedBy: new iam.ServicePrincipal("apigateway.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AmazonAPIGatewayPushToCloudWatchLogs"),
      ],
    });

    // Set the CloudWatch Logs role at account level for API Gateway
    new apigw.CfnAccount(this, "ApiGatewayAccount", {
      cloudWatchRoleArn: apiGatewayLogRole.roleArn,
    });

    const api = new apigw.RestApi(this, "MedGuardApi", {
      restApiName: "medguard-gateway",
      deployOptions: {
        stageName: "prod",
        throttlingRateLimit: 50,
        throttlingBurstLimit: 100,
        metricsEnabled: true,
        loggingLevel: apigw.MethodLoggingLevel.INFO,
        accessLogDestination: new apigw.LogGroupLogDestination(
          new logs.LogGroup(this, "ApiGatewayAccessLogs", {
            retention: logs.RetentionDays.ONE_MONTH,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
          })
        ),
        accessLogFormat: apigw.AccessLogFormat.jsonWithStandardFields(),
        dataTraceEnabled: false,
      },
      endpointConfiguration: {
        // For hospital/internal usage you may want PRIVATE + VPC endpoint + resource policy.
        // Start with REGIONAL for ease; harden to PRIVATE later.
        types: [apigw.EndpointType.REGIONAL],
      },
    });

    const v1 = api.root.addResource("v1");
    const chat = v1.addResource("chat");

    const lambdaIntegration = new apigw.LambdaIntegration(gatewayFn, {
      proxy: true,
    });

    // Conditionally add authentication
    if (enableAuth && userPool) {
      // Cognito Authorizer
      const authorizer = new apigw.CognitoUserPoolsAuthorizer(this, "MedGuardAuthorizer", {
        cognitoUserPools: [userPool],
        identitySource: "method.request.header.Authorization",
      });

      chat.addMethod("POST", lambdaIntegration, {
        authorizationType: apigw.AuthorizationType.COGNITO,
        authorizer,
      });
    } else {
      // No authentication for testing
      chat.addMethod("POST", lambdaIntegration, {
        authorizationType: apigw.AuthorizationType.NONE,
      });
    }

    new cdk.CfnOutput(this, "ApiUrl", { value: api.url });
    new cdk.CfnOutput(this, "AuditBucketName", { value: auditBucket.bucketName });
    new cdk.CfnOutput(this, "AuditTableName", { value: auditTable.tableName });
    if (enableAuth && userPool && userPoolClient) {
      new cdk.CfnOutput(this, "UserPoolId", { value: userPool.userPoolId });
      new cdk.CfnOutput(this, "UserPoolClientId", { value: userPoolClient.userPoolClientId });
    }
  }
}


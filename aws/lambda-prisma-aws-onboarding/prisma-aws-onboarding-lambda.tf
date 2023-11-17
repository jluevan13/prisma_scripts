variable "stack_id" {
  default     = "<SAMPLE STACK NAME>" /// update with stack used to update prisma role
  description = "cloudformation stack id for prisma onboarding"
}

variable "root_id" {
  default     = "r-<OU>" /// update with root ou
  description = "root ou for aws organization"
}

variable "awsAccount" {
  default     = "<ACCOUNT NUMBER>" /// update with account number of aws org
  description = "aws account where prisma is onboarded"
}

data "archive_file" "my_lambda_function" {
  source_dir  = "${path.module}/lambda/"
  output_path = "${path.module}/lambda/lambda.zip"
  type        = "zip"
  depends_on  = [null_resource.install_dependencies]
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "update_prisma_stack_lambda_policy"
  description = "update_prisma_stack_lambda_policy"
  policy      = <<EOF
{
"Version": "2012-10-17",
"Statement": [
    {
    "Action": [
        "cloudformation:UpdateStack"
    ],
    "Effect": "Allow",
    "Resource": [
        "arn:aws:cloudformation:us-east-1:<ACCOUNT NUMBER>:stack/<STAC KNAME>/<STACK ID>" /// update with stack arn
    ]
    },
    {
    "Action": [
        "cloudformation:GetTemplateSummary",
        "cloudformation:DescribeStackSet"
    ],
    "Effect": "Allow",
    "Resource": "*"
    },
    {
    "Action": [
        "cloudformation:UpdateStackSet",
        "cloudformation:DescribeStackSetOperation"
    ],
    "Effect": "Allow",
    "Resource": [
      "arn:aws:cloudformation:us-east-1::type/resource/AWS-IAM-ManagedPolicy",
      "arn:aws:cloudformation:us-east-1::type/resource/AWS-IAM-Role",
      "arn:aws:cloudformation:us-east-1:<ACCOUNT>:stackset/<STACKSET NAME>:<STACK SET ID>" /// update with stack set arn
      ]
    },
    {
    "Action": [
        "secretsmanager:DescribeSecret",
        "secretsmanager:GetRandomPassword",
        "secretsmanager:GetResourcePolicy",
        "secretsmanager:GetSecretValue",
        "secretsmanager:ListSecretVersionIds"
    ],
    "Effect": "Allow",
    "Resource": [
        "arn:aws:secretsmanager:us-east-1:<ACCOUNT>:secret:<SECRET ID>", /// update with secret arn
        "arn:aws:secretsmanager:us-east-1:<ACCOUNT>:secret:<SECRET ID>" /// update with secret arn
    ]
    },
    {
    "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
    ],
    "Effect": "Allow",
    "Resource": "*"
    },
    {
    "Action": [
        "iam:ListPolicyVersions",
        "iam:CreatePolicy",
        "iam:CreatePolicyVersion",
        "iam:DeletePolicyVersion",
        "iam:GetPolicy",
        "iam:DeletePolicy",
        "iam:AttachRolePolicy",
        "iam:GetRole"
    ],
    "Effect": "Allow",
    "Resource": "*"
    }
]
}
EOF
}

resource "aws_iam_role" "prisma-update-function-role" {
  name               = "update_prisma_stack_lambda"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "terraform_lambda_iam_policy_basic_execution" {
  role       = aws_iam_role.prisma-update-function-role.id
  policy_arn = aws_iam_policy.lambda_policy.arn
}

// Allow CloudWatch to invoke our function
resource "aws_lambda_permission" "allow_cloudwatch_to_invoke" {
  function_name = aws_lambda_function.update-prisma-stack.function_name
  statement_id  = "CloudWatchInvoke"
  action        = "lambda:InvokeFunction"

  source_arn = aws_cloudwatch_event_rule.every_15day.arn
  principal  = "events.amazonaws.com"
}

// Create the "cron" schedule
resource "aws_cloudwatch_event_rule" "every_15day" {
  name                = "15Day"
  schedule_expression = "rate(15 days)"
}

// Set the action to perform when the event is triggered
resource "aws_cloudwatch_event_target" "invoke_lambda" {
  rule = aws_cloudwatch_event_rule.every_15day.name
  arn  = aws_lambda_function.update-prisma-stack.arn
}

resource "aws_lambda_function" "update-prisma-stack" {
  filename         = "./lambda/lambda.zip"
  source_code_hash = data.archive_file.my_lambda_function.output_base64sha256
  function_name    = "update-prisma-onboarding-stack"
  role             = aws_iam_role.prisma-update-function-role.arn
  handler          = "index.handler"
  runtime          = "python3.10"
  environment {
    variables = {
      STACK_ID   = "${var.stack_id}",
      ROOTOU     = "${var.root_id}"
      AWSACCOUNT = "${var.awsAccount}"
    }
  }
}

resource "null_resource" "install_dependencies" {
  provisioner "local-exec" {
    command = "pip3 install -r ./lambda/requirements.txt -t ./lambda/"
  }

  triggers = {
    dependencies_versions = filemd5("./lambda/requirements.txt")
    source_versions       = filemd5("./lambda/index.py")
  }
}

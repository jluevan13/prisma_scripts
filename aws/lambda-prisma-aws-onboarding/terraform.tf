terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket  = "prisma-onboarding-<SAMPLE-BUCKET-NAME>"                   /// Update with bucket name
    key     = "prisma-onboarding-<SAMPLE-FOLDER-NAME>/terraform.tfstate" /// Update with folder name
    region  = "us-east-1"
    profile = "personal" /// update with profile used
  }
}

provider "aws" {
  region                   = "us-east-1"
  profile                  = "personal"
  shared_credentials_files = ["/Users/<USER NAME>/.aws/credentials"] /// update with location of aws credentials
}


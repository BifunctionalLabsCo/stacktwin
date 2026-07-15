# Nebius pipeline setup

This optional guide reproduces StackTwin's live content pipeline. The evaluator
quick start in the root README does not need any of these credentials.

## 1. Create storage credentials

Create a Nebius Object Storage bucket and a service account with read/write
access to that bucket. Then create an access key for the service account.

```bash
nebius storage bucket create \
  --name <globally-unique-bucket-name> \
  --parent-id <project-id>
nebius iam service-account create \
  --name stacktwin-storage \
  --parent-id <project-id>
nebius iam access-key create \
  --name stacktwin-storage-key \
  --parent-id <project-id> \
  --account-service-account-id <service-account-id>
```

Grant the service account Object Storage read/write access to the bucket in the
Nebius console. Save the access-key secret immediately and never commit it.

## 2. Configure `.env`

Copy `.env.example` to `.env`, then replace the placeholder values below.

```env
STACKTWIN_APP_MODE=local
STACKTWIN_JOB_IMAGE=cr.eu-north1.nebius.cloud/<registry-path>/stacktwin-job:dev
STACKTWIN_JOB_SUBNET_ID=<subnet-id>
STACKTWIN_JOB_ENV_FILE=.env
STACKTWIN_JOB_MODEL=Qwen/Qwen3-0.6B

NEBIUS_S3_BUCKET=<bucket-name>
NEBIUS_S3_REGION=eu-north1
NEBIUS_S3_ENDPOINT=https://storage.eu-north1.nebius.cloud
NEBIUS_S3_ACCESS_KEY_ID=<access-key-id>
NEBIUS_S3_SECRET_ACCESS_KEY=<secret-access-key>
NEBIUS_S3_PREFIX=stacktwin
```

`NEBIUS_API_KEY` is optional and only used by CV/document profile extraction.
Manual twin creation and the finite Qwen Job flow do not require it.

## 3. Build the worker image

Install and authenticate the Nebius CLI, then configure its Docker credential
helper and publish the worker image:

```bash
nebius registry configure-helper
docker build --platform linux/amd64 \
  -f backend/stacktwin/pipeline/Dockerfile \
  -t cr.eu-north1.nebius.cloud/<registry-path>/stacktwin-job:dev .
docker push cr.eu-north1.nebius.cloud/<registry-path>/stacktwin-job:dev
```

The first authenticated visit after Monday UTC starts one shared prefetch Job.
Generate then starts a finite L40S Job for the selected twin. Jobs persist their
content snapshot, scoring checkpoint, digest, and track in Object Storage and
exit when complete.

For a small live test, add these optional limits to `.env`:

```env
SOURCE_LIMIT=5
DIGEST_SIZE=3
```

Inspect a run with:

```bash
nebius ai job get <job-id>
nebius ai job logs <job-id> --follow
```

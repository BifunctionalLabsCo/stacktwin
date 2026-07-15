# Optional Nebius pipeline and deployment

This guide is only needed for live content generation or cloud deployment. The
local evaluation path in the root README does not require Nebius credentials.

## Live pipeline configuration

The bucket is not bundled with the repository. An evaluator can create their
own isolated bucket and access key, then use the same application flow.

1. In Nebius, create an Object Storage bucket and a service account with
   read/write access to that bucket. Create an access key for that service
   account and save its secret value once.

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

   Grant that service account Object Storage read/write access to the new
   bucket in the Nebius console before using its access key. Keep the access-key
   secret in `.env` or a secret manager, never in Git.

2. Append the following values to the local `.env` created from
   `.env.example`. Do not commit that file.

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

`NEBIUS_API_KEY` is optional and only needed for CV or document-based profile
extraction. Manual twin creation and the finite Qwen Job pipeline do not need
it.

when worker code changes:
3. Install and authenticate the Nebius CLI, then build and push the worker
   image when worker code changes:
when worker code changes:

```bash
nebius registry configure-helper
docker build --platform linux/amd64 \
  -f backend/stacktwin/pipeline/Dockerfile \
  -t cr.eu-north1.nebius.cloud/<registry-path>/stacktwin-job:dev .
docker push cr.eu-north1.nebius.cloud/<registry-path>/stacktwin-job:dev
```

The first visit after Monday UTC starts one shared prefetch Job. A learner's
Generate action starts a finite L40S Job for that twin. Jobs persist the shared
snapshot, score checkpoints, digest, and track to Object Storage, then exit.

## Web image

The user-facing application has its own CPU-only image:

```bash
docker buildx build --load --platform linux/amd64 \
  -f backend/stacktwin/api/Dockerfile \
  -t cr.eu-north1.nebius.cloud/<registry-path>/stacktwin-web:dev .
docker push cr.eu-north1.nebius.cloud/<registry-path>/stacktwin-web:dev
```

For deployment, attach a Nebius service account to the web VM and keep runtime
credentials in MysteryBox. The VM retrieves the web and Job environment files
at boot; the image must never contain a `.env`, storage credential, or user
token. Build the production web image with
`NEXT_PUBLIC_STACKTWIN_DEMO_MODE=false` so it reads generated tracks.

## Fast development run

For a small live run, set these optional values in `.env`:

```env
SOURCE_LIMIT=5
DIGEST_SIZE=3
```

Watch a submitted Job with:

```bash
nebius ai job get <job-id>
nebius ai job logs <job-id> --follow
```

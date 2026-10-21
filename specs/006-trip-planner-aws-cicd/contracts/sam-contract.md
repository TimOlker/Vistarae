# AWS SAM Infrastructure Contract: Phase 6

**Feature Identifier**: `006-trip-planner-aws-cicd`  
**Date**: 2026-10-20  
**Target Region**: `us-east-2`  
**Template File**: `template.yaml`

---

## 1. CloudFront Edge & Origin Mapping Contract

```text
Viewer Request: https://*.cloudfront.net/*
│
├── CacheBehavior: Default (*)
│   ├── Origin: Private S3 Bucket (VistaraeSpaBucket) via OAC
│   ├── FunctionAssociations:
│   │   └── EventType: viewer-request
│   │       Function: SpaRouterFunction (spa-router.js)
│   ├── CachePolicy: Managed-CachingOptimized (658327ea-f89d-4fab-a63d-7e88639e58f6)
│   └── ViewerProtocolPolicy: redirect-to-https
│
└── CacheBehavior: /api/*
    ├── Origin: API Gateway HTTP API ({api-id}.execute-api.us-east-2.amazonaws.com)
    ├── CachePolicy: Managed-CachingDisabled (4135ea2d-6df8-44a3-9df3-4b5a84be39ad)
    ├── OriginRequestPolicy: Managed-AllViewerExceptHostHeader (b689b0a8-53d0-40ab-baf2-68738e2966ac)
    ├── AllowedMethods: [GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE]
    └── ViewerProtocolPolicy: https-only
```

### Edge Function Logic (`spa-router.js`)

```javascript
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  // Check if the request is an extensionless SPA path and not an API call
  if (!uri.includes(".") && !uri.startsWith("/api/")) {
    request.uri = "/index.html";
  }
  return request;
}
```

---

## 2. Domain Lambda Matrix & Least-Privilege IAM Policies

| Lambda Logical ID     |   Memory   | Timeout |   Runtime / Arch    | Trigger / Routing                                                 | IAM Policy Grants                                                                                                                              |
| :-------------------- | :--------: | :-----: | :-----------------: | :---------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------- |
| **PoiFunction**       | 512–1024MB |   15s   | Python 3.12 / arm64 | HTTP API `/api/pois/*`, `/api/itineraries/*`                      | Neon Secret Read, X-Ray Write                                                                                                                  |
| **UserFunction**      |   256MB    |   10s   | Python 3.12 / arm64 | HTTP API `/api/users/*`, `/api/auth/*`                            | Neon Secret Read, Cognito Verify, X-Ray Write                                                                                                  |
| **IngestFunction**    |   256MB    |   15s   | Python 3.12 / arm64 | HTTP API `/api/ingest/*`                                          | `sqs:SendMessage` on IngestQueue, Neon Secret Read, X-Ray Write                                                                                |
| **AdminFunction**     |   256MB    |   10s   | Python 3.12 / arm64 | HTTP API `/api/admin/*`                                           | Neon Secret Read, X-Ray Write                                                                                                                  |
| **BatchIngestWorker** |   512MB    |   30s   | Python 3.12 / arm64 | SQS EventSourceMapping (`BatchSize: 10`, `MaximumConcurrency: 2`) | `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` on IngestQueue, Neon Secret Read, X-Ray Write                              |
| **SpendKillSwitch**   |   128MB    |   10s   | Python 3.12 / arm64 | SNS Topic `SpendAlertTopic` (AWS Budgets $15.00)                  | `lambda:PutFunctionConcurrency`, `lambda:UpdateEventSourceMapping`, `apigateway:PATCH`/`apigateway:UpdateStage`, Neon Secret Read, X-Ray Write |

### SpendKillSwitch SNS Event Contract

```json
{
  "Records": [
    {
      "EventSource": "aws:sns",
      "EventVersion": "1.0",
      "Sns": {
        "Type": "Notification",
        "MessageId": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
        "TopicArn": "arn:aws:sns:us-east-2:123456789012:vistarae-spend-alert-topic",
        "Subject": "AWS Budget Notification: Vistarae-Monthly-Budget",
        "Message": "{\"budget\": {\"budgetName\": \"Vistarae-Monthly-Budget\", \"budgetLimit\": {\"amount\": \"15.0\", \"unit\": \"USD\"}}, \"cost\": {\"amount\": \"15.02\", \"unit\": \"USD\"}}",
        "Timestamp": "2026-10-20T18:00:00.000Z"
      }
    }
  ]
}
```

---

## 3. CloudWatch Free-Tier Monitoring Contract (<10 Alarms)

1. **Log Metric Filter**:
   - Filter Pattern: `{ $.level = "ERROR" }`
   - Metric Name: `ApplicationErrorCount`
   - Metric Namespace: `Vistarae/Errors`
2. **Alarm 1 — Application Error Surge**:
   - Metric: `Vistarae/Errors/ApplicationErrorCount`
   - Threshold: $\ge 5$ errors in 5 minutes
   - Action: Publish to `DeveloperAlertTopic` SNS
3. **Alarm 2 — SQS Dead-Letter Queue Depth**:
   - Metric: `AWS/SQS/ApproximateNumberOfMessagesVisible` on `vistarae-ingest-dlq`
   - Threshold: $\ge 1$ message visible
   - Action: Publish to `DeveloperAlertTopic` SNS
4. **AWS X-Ray Custom Sampling Rule**:
   - FixedRate: 0.01 (1%)
   - ReservoirSize: 0
   - ServiceType: `*`
   - Guaranteed Monthly Traces: $< 10,000$ (well inside the 100,000 monthly free tier).

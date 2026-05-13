# AWS 部署指南

## 前置要求

1. AWS 帳戶和 CLI 配置
2. Docker 和 Docker Hub 帳戶
3. 必要的 IAM 權限

## 步驟 1: 準備環境變數

創建 `.env.production` 檔案：

```bash
cp .env.example .env.production
# 填入生產環境的環境變數
```

## 步驟 2: 構建和推送 Docker 映像

```bash
# 構建 Docker 映像
docker build -t pcb-bot:latest .

# 為 ECR 打標籤
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <your-account-id>.dkr.ecr.us-east-1.amazonaws.com

docker tag pcb-bot:latest <your-account-id>.dkr.ecr.us-east-1.amazonaws.com/pcb-bot:latest

# 推送到 ECR
docker push <your-account-id>.dkr.ecr.us-east-1.amazonaws.com/pcb-bot:latest
```

## 步驟 3: 部署 CloudFormation 棧

```bash
# 部署棧
aws cloudformation create-stack \
  --stack-name pcb-bot-stack \
  --template-body file://aws/cloudformation.yaml \
  --parameters \
    ParameterKey=EnvironmentName,ParameterValue=prod \
    ParameterKey=ContainerImage,ParameterValue=<your-account-id>.dkr.ecr.us-east-1.amazonaws.com/pcb-bot:latest \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

## 步驟 4: 設置 LINE Bot Webhook

1. 前往 LINE Developers Console
2. 設定 Webhook URL 為 ALB DNS：
   ```
   https://<load-balancer-dns>/callback
   ```

## 步驟 5: 配置自動擴展

```bash
# 創建 AutoScaling 目標
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/pcb-bot-cluster/pcb-bot-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10 \
  --region us-east-1

# 創建 scaling policy
aws application-autoscaling put-scaling-policy \
  --policy-name pcb-bot-cpu-scaling \
  --service-namespace ecs \
  --resource-id service/pcb-bot-cluster/pcb-bot-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration \
    TargetValue=70.0,PredefinedMetricSpecification={PredefinedMetricType=ECSServiceAverageCPUUtilization},ScaleOutCooldown=300,ScaleInCooldown=300 \
  --region us-east-1
```

## 監控和日誌

### CloudWatch 日誌
```bash
aws logs tail /ecs/pcb-bot --follow
```

### 檢查 ECS 服務狀態
```bash
aws ecs describe-services \
  --cluster pcb-bot-cluster \
  --services pcb-bot-service \
  --region us-east-1
```

## 成本優化建議

1. 使用 RDS Reserved Instances 節省 30-40%
2. 使用 Fargate Spot 運行非關鍵任務
3. 配置 S3 生命週期策略自動刪除舊導出檔案
4. 使用 ElastiCache 自動故障轉移

## 故障排查

### 應用無法連接資料庫
```bash
# 檢查安全組規則
aws ec2 describe-security-groups --group-ids sg-xxxxx

# 檢查 RDS 日誌
aws rds describe-db-instances --db-instance-identifier pcb-bot-db
```

### 高延遲問題
1. 檢查 CloudWatch 指標
2. 考慮增加 ECS 任務數
3. 優化資料庫查詢

## 回滾部署

```bash
# 回到前一個版本
aws ecs update-service \
  --cluster pcb-bot-cluster \
  --service pcb-bot-service \
  --force-new-deployment \
  --region us-east-1
```

## 更新應用

```bash
# 構建新版本
docker build -t pcb-bot:vX.Y.Z .

# 推送到 ECR
docker push <your-account-id>.dkr.ecr.us-east-1.amazonaws.com/pcb-bot:vX.Y.Z

# 更新 ECS 任務定義
aws ecs update-service \
  --cluster pcb-bot-cluster \
  --service pcb-bot-service \
  --force-new-deployment \
  --region us-east-1
```

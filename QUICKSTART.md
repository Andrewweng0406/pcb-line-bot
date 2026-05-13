# 快速開始指南

## 立即開始（3 分鐘）

### 1️⃣ 準備環境

```bash
# 複製環境變數範例
cp .env.example .env

# 編輯 .env，添加你的 LINE Bot 憑證
nano .env
```

**必需的環境變數：**
```env
LINE_CHANNEL_ACCESS_TOKEN=你的token
LINE_CHANNEL_SECRET=你的secret
OPENAI_API_KEY=你的openai_api_key
```

### 2️⃣ 使用 Docker 啟動（推薦）

```bash
# 啟動所有服務（PostgreSQL + Redis + 應用）
docker-compose up

# 等待看到這條訊息：
# app_1  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

✅ 應用現在運行於 `http://localhost:8000`

### 3️⃣ 不使用 Docker 啟動

```bash
# 安裝依賴
pip install -r requirements.txt

# 啟動應用（使用 SQLite）
DATABASE_URL=sqlite:///./test.db \
uvicorn app.main:app --reload --port 8000
```

✅ 應用現在運行於 `http://localhost:8000`

---

## 配置 LINE Webhook

### 在本機測試

1. **安裝 ngrok**
   ```bash
   brew install ngrok
   ```

2. **啟動 ngrok**
   ```bash
   ngrok http 8000
   # 複製輸出的 HTTPS URL，例如：
   # https://xxxx.ngrok-free.app
   ```

3. **設置 LINE Developers Webhook**
   - 前往 [LINE Developers Console](https://developers.line.biz/)
   - 進入你的 Channel
   - 設置 `Webhook URL` 為：
     ```
     https://xxxx.ngrok-free.app/callback
     ```
   - 啟用 Webhook

4. **在 LINE 測試**
   - 掃描 QR Code 添加你的 Bot
   - 發送訊息：`46L Megtron 6 100x100mm 10pcs ENIG 5u`
   - Bot 應該立即回覆報價

---

## 快速測試

### 通過 API 測試

```bash
# 測試報價文字
curl "http://localhost:8000/quote_text?text=4L%20FR4%20100x100mm%20100pcs"

# 檢查應用健康狀況
curl http://localhost:8000/health

# 查看 API 文檔
open http://localhost:8000/docs
```

### 查看日誌

```bash
# 實時查看日誌（Docker）
docker-compose logs -f app

# 或查看日誌檔案
tail -f logs/pcb_bot_*.log
```

---

## 本地開發工作流

### 修改代碼後自動重載

```bash
# 使用 --reload 旗標（已在 docker-compose 中設置）
uvicorn app.main:app --reload --port 8000
```

### 進入 Python Shell 進行測試

```bash
python3 << 'EOF'
from app.quote_engine import calculate_quote

parsed = {
    'layer': 4,
    'material': 'FR4',
    'length_mm': 100,
    'width_mm': 100,
    'qty': 100
}

result = calculate_quote(parsed)
print(f"Total: ${result['total']}")
print(f"Per Unit: ${result['unit_price']}")
EOF
```

---

## 部署到 AWS（15 分鐘）

### 準備工作

1. **AWS 帳戶和 CLI 設置**
   ```bash
   aws configure
   # 輸入 Access Key ID、Secret Access Key 和 Region
   ```

2. **建立 ECR Repository**
   ```bash
   aws ecr create-repository --repository-name pcb-bot
   ```

3. **建立 RDS 資料庫密碼**
   ```bash
   aws secretsmanager create-secret \
     --name pcb-bot-db-password \
     --secret-string '{"password":"YourSecurePassword123!"}'
   ```

### 部署

1. **構建和推送 Docker 映像**
   ```bash
   # 獲取登錄憑證
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin \
     <your-account-id>.dkr.ecr.us-east-1.amazonaws.com

   # 構建映像
   docker build -t pcb-bot:latest .

   # 標籤
   docker tag pcb-bot:latest \
     <your-account-id>.dkr.ecr.us-east-1.amazonaws.com/pcb-bot:latest

   # 推送
   docker push \
     <your-account-id>.dkr.ecr.us-east-1.amazonaws.com/pcb-bot:latest
   ```

2. **部署 CloudFormation 棧**
   ```bash
   aws cloudformation create-stack \
     --stack-name pcb-bot-prod \
     --template-body file://aws/cloudformation.yaml \
     --parameters \
       ParameterKey=ContainerImage,ParameterValue=<your-account-id>.dkr.ecr.us-east-1.amazonaws.com/pcb-bot:latest \
       ParameterKey=EnvironmentName,ParameterValue=prod \
     --capabilities CAPABILITY_NAMED_IAM \
     --region us-east-1
   ```

3. **等待部署完成**
   ```bash
   aws cloudformation wait stack-create-complete \
     --stack-name pcb-bot-prod \
     --region us-east-1

   # 獲取負載均衡器 DNS
   aws cloudformation describe-stacks \
     --stack-name pcb-bot-prod \
     --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' \
     --output text
   ```

4. **更新 LINE Webhook URL**
   - 使用上面獲取的 DNS 名稱
   - 在 LINE Developers 中設置：
     ```
     https://<your-load-balancer-dns>/callback
     ```

---

## 故障排查

### Docker 無法啟動

```bash
# 檢查日誌
docker-compose logs app

# 清理並重新啟動
docker-compose down
docker-compose up --build
```

### 資料庫連接失敗

```bash
# 檢查 PostgreSQL 狀態
docker-compose logs postgres

# 確保 DATABASE_URL 正確
echo $DATABASE_URL
```

### 應用 500 錯誤

```bash
# 查看詳細日誌
cat logs/pcb_bot_*.log

# 或通過 API 文檔測試
open http://localhost:8000/docs
```

### 圖片解析失敗

- 檢查 `OPENAI_API_KEY` 是否有效
- 檢查 OpenAI 帳戶配額
- 確保圖片格式為 JPG/PNG（< 10MB）

---

## 環境變數快速參考

| 變數 | 範例 | 必需 | 說明 |
|------|------|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | `ey...` | ✅ | LINE Bot 存取 token |
| `LINE_CHANNEL_SECRET` | `ab...` | ✅ | LINE Channel Secret |
| `OPENAI_API_KEY` | `sk-...` | ✅ | OpenAI API 金鑰 |
| `DATABASE_URL` | `postgresql://...` | ❌ | 資料庫 URL（預設 SQLite） |
| `REDIS_ENABLED` | `true` | ❌ | 啟用 Redis（預設 false） |
| `REDIS_URL` | `redis://localhost` | ❌ | Redis 連接 URL |
| `AWS_ENABLED` | `true` | ❌ | 啟用 AWS S3（預設 false） |
| `AWS_S3_BUCKET` | `my-bucket` | ❌ | S3 bucket 名稱 |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | ❌ | 公開 URL（用於下載連結） |
| `DEBUG` | `False` | ❌ | 調試模式（預設 False） |

---

## 常見命令

```bash
# 啟動應用
docker-compose up

# 後台運行
docker-compose up -d

# 停止應用
docker-compose down

# 查看日誌
docker-compose logs -f app

# 進入容器 shell
docker-compose exec app bash

# 重建容器
docker-compose up --build

# 清理所有資料
docker-compose down -v
```

---

## 下一步

1. ✅ 完成快速開始
2. 📖 閱讀 [README.md](README.md) 了解更多功能
3. 📊 查看 [IMPROVEMENTS.md](IMPROVEMENTS.md) 了解架構升級
4. ☁️ 參考 [aws/DEPLOYMENT.md](aws/DEPLOYMENT.md) 部署到 AWS
5. 🔐 在生產前設置 HTTPS 和速率限制

---

## 需要幫助？

- 查看日誌：`docker-compose logs app`
- 檢查健康狀況：`curl http://localhost:8000/health`
- 查看 API 文檔：`http://localhost:8000/docs`
- 閱讀代碼註解
- 檢查 .env.example 中的說明

---

## 現在就開始！

```bash
# 複製一行命令，立即開始
docker-compose up
```

祝你使用愉快！ 🚀

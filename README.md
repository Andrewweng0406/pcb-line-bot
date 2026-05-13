# PCB Quote Bot v2.0

AI 驅動的 PCB 報價機器人，集成 LINE 平台，支持文字和圖片識別。

## 特性

- ✅ 實時 PCB 報價計算
- ✅ 文字規格解析（使用 OpenAI）
- ✅ PCB 圖片識別和解析
- ✅ 報價歷史記錄查詢
- ✅ 平均價格統計
- ✅ Excel 和正式報價單匯出
- ✅ 用戶記憶存儲（支持 Redis）
- ✅ S3 檔案存儲支持
- ✅ 完整的 error handling 和日誌
- ✅ Docker 和 AWS Fargate 就緒

## 技術棧

- **後端**: FastAPI + Uvicorn
- **資料庫**: PostgreSQL（RDS）
- **快取**: Redis（ElastiCache）
- **檔案存儲**: S3
- **容器化**: Docker + Docker Compose
- **基礎設施**: AWS CloudFormation
- **監控**: CloudWatch

## 本機開發

### 使用 Docker Compose（推薦）

```bash
# 複製環境變數檔案
cp .env.example .env

# 編輯 .env，添加 LINE Bot 和 OpenAI 憑證
nano .env

# 啟動服務
docker-compose up

# 應用將在 http://localhost:8000 可用
```

### 不使用 Docker

```bash
# 安裝依賴
pip install -r requirements.txt

# 複製環境變數
cp .env.example .env

# 編輯 .env，設置本地資料庫
DATABASE_URL=sqlite:///./quotes.db

# 初始化資料庫
python -c "from app.core.database import init_db; init_db()"

# 啟動應用
uvicorn app.main:app --reload --port 8000
```

## 本機測試

### 測試報價文字端點

```bash
curl "http://localhost:8000/quote_text?text=46L%20Megtron%206%20109.5x59.5mm%202pcs%20ENIG%2010u%20VIP%20impedance%20back%20drill%20BVH"
```

### 測試圖片解析

```bash
curl http://localhost:8000/image_test
```

### 使用 ngrok 測試 LINE Webhook

```bash
# 安裝 ngrok
brew install ngrok

# 啟動 ngrok
ngrok http 8000

# 複製 HTTPS 網址，在 LINE Developers 設置 Webhook URL
# 例如: https://xxxx.ngrok-free.app/callback
```

## 環境變數

詳見 `.env.example`，主要變數：

```env
# LINE Bot
LINE_CHANNEL_ACCESS_TOKEN=xxx
LINE_CHANNEL_SECRET=xxx

# OpenAI（用於文字/圖片解析）
OPENAI_API_KEY=sk-xxx

# 資料庫
DATABASE_URL=postgresql://user:pass@localhost/pcb_bot

# Redis（可選）
REDIS_ENABLED=True
REDIS_URL=redis://localhost:6379

# AWS S3（可選）
AWS_ENABLED=True
AWS_S3_BUCKET=your-bucket
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx

# 公開 URL（用於下載連結）
PUBLIC_BASE_URL=http://localhost:8000
```

## API 端點

### 健康檢查
```
GET /health
GET /
```

### 報價
```
GET /quote_text?text=...
```

### LINE Webhook
```
POST /callback
```

### 檔案下載
```
GET /download/exports/{filename}
```

## LINE Bot 指令

| 指令 | 功能 |
|------|------|
| PCB 規格文字 | 解析並計算報價 |
| 上傳 PCB 圖片 | 識別規格並計算報價 |
| 查詢報價 | 顯示最近 5 筆報價 |
| 匯出報價單 | 生成 Excel 檔案 |
| 正式報價單 | 生成正式報價單 |
| 查詢 [Layer/材料] | 搜尋歷史報價 |
| 平均 [Layer/材料] | 查詢平均價格 |
| 結束/reset/清除 | 清除當前報價 |

### 範例 PCB 規格文字

```
46L Megtron 6 109.5x59.5mm 2pcs ENIG 10u VIP impedance back drill BVH
```

解析結果：
- Layer: 46L
- Material: Megtron 6
- Size: 109.5 x 59.5 mm
- Qty: 2 pcs
- Surface Finish: ENIG 10μ"
- 特殊製程: VIP, Impedance, Back Drill, BVH

## 部署到 AWS

詳見 [AWS 部署指南](aws/DEPLOYMENT.md)

快速概要：
```bash
# 1. 構建和推送 Docker 映像
docker build -t pcb-bot:latest .
docker push <ecr-uri>/pcb-bot:latest

# 2. 部署 CloudFormation 棧
aws cloudformation create-stack \
  --stack-name pcb-bot-stack \
  --template-body file://aws/cloudformation.yaml \
  --parameters ParameterKey=ContainerImage,ParameterValue=<ecr-uri>/pcb-bot:latest

# 3. 更新 LINE Webhook URL
# 使用 ALB 的 DNS 名稱設置 webhook
```

## 專案結構

```
pcb_line_bot/
├── app/                    # 應用程式
│   ├── core/              # 核心模塊（config、database、memory、storage）
│   ├── main.py            # FastAPI 應用程式
│   ├── quote_engine.py    # 報價計算引擎
│   ├── ai_parser.py       # 文字解析（OpenAI）
│   ├── image_parser.py    # 圖片解析（OpenAI Vision）
│   └── export_*.py        # 檔案匯出
├── aws/                    # AWS 部署配置
│   ├── cloudformation.yaml # CloudFormation 模板
│   └── DEPLOYMENT.md      # 部署指南
├── data/                   # 資料目錄
│   └── uploads/           # 上傳的圖片
├── logs/                   # 應用日誌
├── exports/               # 匯出的檔案
├── docker-compose.yml     # Docker Compose 設置
├── Dockerfile             # Docker 映像定義
├── requirements.txt       # Python 依賴
├── .env.example           # 環境變數範例
└── .gitignore             # Git 忽略列表
```

## 日誌

日誌檔案儲存在 `logs/` 目錄，按日期分檔：
```
logs/
├── pcb_bot_20260512.log
├── pcb_bot_20260513.log
└── ...
```

## 故障排查

### 資料庫連接失敗
```
error: can't connect to database
```
- 檢查 `DATABASE_URL` 是否正確
- 確保資料庫服務運行中
- 檢查防火牆和安全組規則

### LINE Webhook 失敗
- 檢查 `LINE_CHANNEL_ACCESS_TOKEN` 和 `LINE_CHANNEL_SECRET`
- 驗證 webhook URL 是否正確設置
- 檢查應用日誌

### 圖片解析失敗
- 確保 `OPENAI_API_KEY` 已設置
- 檢查 OpenAI 帳戶配額
- 驗證圖片格式和大小

## 性能優化

1. **Redis 快取**: 啟用 `REDIS_ENABLED=True` 來快取用戶記憶
2. **資料庫索引**: 已在 `created_at` 和 `customer_id` 上建立索引
3. **S3 存儲**: 使用 S3 代替本地存儲，支持自動擴展
4. **連接池**: 配置的連接池大小為 10

## 安全性

- 環境變數不提交到 Git（見 `.gitignore`）
- 使用 AWS Secrets Manager 管理生產機密
- 安全組限制資料庫和快取訪問
- S3 bucket 設置為私有，使用簽署 URL 進行下載

## 監控

- CloudWatch 日誌整合
- 健康檢查端點 `/health`
- ECS 任務級別的 CPU/記憶體監控

## 支持和反饋

有問題或改進建議？請提交 Issue 或 Pull Request。

## 授權

MIT License

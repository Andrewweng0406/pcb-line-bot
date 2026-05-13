# AWS 免費版部署指南 - 完全免費！

**月費: $0** (12 個月內)

---

## 🎯 AWS 免費版包含什麼

### ✅ 可免費使用

| 服務 | 免費額度 | 夠用嗎 |
|------|---------|--------|
| **EC2 t2.micro** | 750 小時/月 | ✅ 足夠 24/7 運行 |
| **RDS db.t2.micro** | 750 小時/月 | ✅ 足夠數據庫 |
| **S3** | 5GB 存儲 + 20K GET | ✅ 足夠 |
| **Lambda** | 100 萬次調用 | ✅ 足夠 |
| **DynamoDB** | 25GB | ✅ 足夠 |

### ❌ 不免費（我們不需要）

| 服務 | 原因 |
|------|------|
| ElastiCache | 用本地記憶代替 |
| ALB | 用 Nginx 反向代理代替 |
| ECS Fargate | 用 EC2 代替 |

---

## 💡 最佳方案（完全免費）

### 選項 A：**EC2 + RDS**（推薦）
```
┌─────────────────────────────┐
│ EC2 t2.micro (免費)         │
│ ├─ Docker + 應用程序        │
│ └─ Nginx (反向代理)         │
├─────────────────────────────┤
│ RDS db.t2.micro (免費)      │
│ └─ PostgreSQL 資料庫        │
├─────────────────────────────┤
│ S3 (5GB 免費)               │
│ └─ 匯出檔案存儲             │
└─────────────────────────────┘

成本: $0/月
```

### 選項 B：**Lambda + DynamoDB**（輕量級）
```
┌─────────────────────────────┐
│ Lambda (100 萬調用免費)      │
│ └─ 應用程序                  │
├─────────────────────────────┤
│ API Gateway (免費)          │
│ └─ REST API 端點             │
├─────────────────────────────┤
│ DynamoDB (25GB 免費)        │
│ └─ 用戶記憶 + 報價紀錄       │
├─────────────────────────────┤
│ S3 (5GB 免費)               │
│ └─ 匯出檔案存儲             │
└─────────────────────────────┘

成本: $0/月
優點: 按使用付費，超級便宜
缺點: 首次啟動慢（冷啟動）
```

---

## 🚀 推薦：使用 EC2 + RDS 免費方案

### 第 1 步：創建 EC2 實例

1. 登錄 AWS 控制台
2. 進入 EC2 → 實例 → 啟動實例
3. 選擇 Ubuntu 20.04 LTS (免費符合條件)
4. 實例類型: **t2.micro** (預選，免費)
5. 存儲: **30GB** (免費層包含 30GB)
6. 安全組: 允許：
   - SSH (22 端口)
   - HTTP (80 端口)
   - HTTPS (443 端口)
7. 啟動

### 第 2 步：創建 RDS 資料庫

1. 進入 RDS → 資料庫 → 創建資料庫
2. 引擎: PostgreSQL 15
3. 實例類別: **db.t2.micro** (免費)
4. 分配的存儲: **20GB** (免費層)
5. 備份: 設置 7 天
6. 創建資料庫

**記下**:
- 資料庫端點 (endpoint)
- 主用戶名和密碼
- 資料庫名稱

### 第 3 步：連接 EC2

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

### 第 4 步：安裝應用

```bash
# 更新系統
sudo apt-get update
sudo apt-get upgrade -y

# 安裝 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# 安裝 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 安裝 Git
sudo apt-get install git -y

# Clone 你的代碼
git clone your-repository-url.git
cd pcb_line_bot
```

### 第 5 步：配置應用

```bash
# 創建 .env 檔案
cp .env.example .env

# 編輯環境變數
nano .env
```

**設置以下變數**:
```env
DEBUG=False
LINE_CHANNEL_ACCESS_TOKEN=你的token
LINE_CHANNEL_SECRET=你的secret
OPENAI_API_KEY=你的openai_key

# 使用 RDS 資料庫
DATABASE_URL=postgresql://username:password@your-rds-endpoint:5432/pcb_bot

# 禁用不需要的功能（節省成本）
REDIS_ENABLED=False
AWS_ENABLED=False

# 公開 URL（稍後設置）
PUBLIC_BASE_URL=http://your-ec2-public-ip
```

### 第 6 步：簡化 docker-compose.yml

由於使用外部 RDS，修改 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  app:
    build: .
    environment:
      DEBUG: "False"
      DATABASE_URL: postgresql://username:password@your-rds-endpoint:5432/pcb_bot
      REDIS_ENABLED: "False"
      AWS_ENABLED: "False"
      PUBLIC_BASE_URL: http://your-ec2-public-ip
      LINE_CHANNEL_ACCESS_TOKEN: ${LINE_CHANNEL_ACCESS_TOKEN}
      LINE_CHANNEL_SECRET: ${LINE_CHANNEL_SECRET}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8000:8000"
    volumes:
      - ./data/uploads:/app/data/uploads
      - ./logs:/app/logs
    restart: always

# 移除 postgres 和 redis 服務
# 因為我們使用外部 RDS
```

### 第 7 步：啟動應用

```bash
# 啟動應用
docker-compose up -d

# 查看日誌
docker-compose logs -f
```

### 第 8 步：設置 Nginx 反向代理（可選但推薦）

```bash
# 安裝 Nginx
sudo apt-get install nginx -y

# 創建配置
sudo nano /etc/nginx/sites-available/pcb-bot
```

**添加以下內容**:
```nginx
server {
    listen 80;
    server_name _;

    # 上傳大小限制
    client_max_body_size 10M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**啟用配置**:
```bash
sudo ln -s /etc/nginx/sites-available/pcb-bot /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### 第 9 步：設置 HTTPS（Let's Encrypt）

```bash
# 安裝 Certbot
sudo apt-get install certbot python3-certbot-nginx -y

# 獲取證書（需要域名）
sudo certbot --nginx -d your-domain.com

# 自動更新
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### 第 10 步：在 LINE Developers 設置 Webhook

```
Webhook URL: https://your-domain.com/callback
（或 http://your-ec2-public-ip/callback 如果沒有域名）
```

---

## 📊 成本分析

### 免費版期間（12 個月）
```
EC2 t2.micro:     $0
RDS db.t2.micro:  $0
S3 (5GB):         $0
────────────────────
總計: $0/月
```

### 12 個月後

**如果保持低使用量** (1 個用戶):
```
EC2 t2.micro (永遠免費層): $0
RDS db.t2.micro (永遠免費層): $0
S3 (超過 5GB): ~$0.23/GB
────────────────────────────
總計: $0-5/月
```

**如果流量增加**:
```
EC2 升級到 t3.small: $10
RDS 升級: $20
S3: $5-10
────────────────────
總計: $35-40/月
```

---

## ⏰ 重要：免費版計時器

AWS 免費版是 **12 個月**：
- 從你首次使用 AWS 開始計算
- 每月檢查使用情況
- 12 個月後自動停止免費，按正常費率計費

**設置預算告警**:
```bash
AWS 控制台 → 計費 → 預算 → 設置警報
設置為: $10/月
```

---

## 🔧 常用命令

### 檢查應用狀態
```bash
docker-compose ps
docker-compose logs -f app
```

### 重啟應用
```bash
docker-compose restart app
```

### 更新應用
```bash
git pull
docker-compose up -d --build
```

### 備份資料庫
```bash
# RDS 自動備份了，但也可以手動
pg_dump -h your-rds-endpoint -U username -d pcb_bot > backup.sql
```

---

## 🛡️ 安全建議

### 1. 安全組配置

```bash
# 只允許必要的端口
SSH (22):   僅允許你的 IP
HTTP (80):  允許所有 (0.0.0.0/0)
HTTPS (443): 允許所有 (0.0.0.0/0)
```

### 2. RDS 安全組

```bash
# 只允許來自 EC2 的連接
PostgreSQL (5432): 允許 EC2 安全組
```

### 3. 定期更新

```bash
# 每月運行一次
sudo apt-get update
sudo apt-get upgrade
```

---

## 📈 何時升級

### 當達到以下條件時考慮升級：

1. **EC2 達到 CPU 100%** → 升級到 t3.small ($10/月)
2. **RDS 達到 70% 容量** → 升級儲存
3. **S3 超過 5GB** → 添加額外儲存 ($0.23/GB)
4. **用戶超過 100** → 添加 Redis ($12/月)

---

## 🎯 快速檢查清單

在部署前檢查：

- [ ] AWS 免費版帳戶已創建
- [ ] EC2 t2.micro 實例已啟動
- [ ] RDS db.t2.micro 已創建
- [ ] 安全組已正確配置
- [ ] SSH 密鑰已下載
- [ ] 可以連接 EC2
- [ ] Docker 已安裝
- [ ] 應用已啟動
- [ ] Nginx 已配置
- [ ] HTTPS 已設置
- [ ] LINE Webhook 已配置
- [ ] 可以在 LINE 接收消息

---

## 💡 優化建議

### 減少成本

1. **使用本地記憶代替 Redis** ✅ 已配置
2. **使用 S3 免費額度** ✅ 足夠
3. **關閉 DEBUG 模式** ✅ 已設置
4. **定期監控成本** ✅ 設置預算告警

### 增加可靠性

1. **啟用 RDS 自動備份** ✅ 7 天保留
2. **啟用 EC2 自動恢復** ✅ 硬件故障恢復
3. **使用 Nginx 反向代理** ✅ 負載均衡
4. **定期更新系統** ✅ 安全補丁

---

## 🆘 故障排查

### 應用無法啟動
```bash
docker-compose logs app
# 檢查 DATABASE_URL 是否正確
```

### 無法連接資料庫
```bash
# 檢查 RDS 安全組
# 確保允許 EC2 的連接
psql -h your-rds-endpoint -U username -d pcb_bot
```

### 查看應用日誌
```bash
docker-compose logs -f app
tail -f logs/pcb_bot_*.log
```

### 重啟應用
```bash
docker-compose down
docker-compose up -d
```

---

## 📊 監控儀表板

### CloudWatch 免費監控

AWS 控制台提供免費的監控：
- EC2 CPU 使用率
- RDS CPU 使用率
- 網絡流量
- 磁盤使用率

**設置** → CloudWatch → 儀表板 → 創建儀表板

---

## 🎉 總結

✨ **使用 AWS 免費版，完全免費運行你的應用 12 個月！**

| 方面 | 免費版 | 12 個月後 |
|------|--------|----------|
| EC2 | 免費 | $10-50/月 |
| RDS | 免費 | $15-30/月 |
| S3 | 免費 (5GB) | $1-10/月 |
| 總計 | **$0** | **$25-90/月** |

---

## 下一步

1. ✅ 創建 EC2 和 RDS 實例
2. ✅ 連接 EC2 並安裝應用
3. ✅ 配置 Nginx 和 HTTPS
4. ✅ 設置 LINE Webhook
5. ✅ 開始使用！

**需要幫助嗎？** 告訴我你遇到的問題，我可以幫你一步步解決！

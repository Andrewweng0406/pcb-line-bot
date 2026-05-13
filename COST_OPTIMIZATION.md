# PCB Quote Bot 成本優化方案

針對小規模使用（1-10 個用戶）的成本優化建議

---

## 📊 成本對比

### 現有方案（企業級）
```
ECS Fargate:        $40
RDS PostgreSQL:     $18
ElastiCache Redis:  $12
ALB:                $25
S3 + CloudWatch:    $16
────────────────────────
總計: $111/月 (年度 $1,330)
```

**問題**: 對於只有 1 個用戶太貴了！

---

## 🎯 推薦方案

### 方案 1：**最便宜** - AWS Lightsail
```
費用: $5-10/月 (年度 $60-120)
省費: 92% ✅

特點:
✅ 內置 PostgreSQL 資料庫
✅ 簡單易管理
✅ 包含 1TB 流量
✅ 自動備份
✅ 固定費用（可預測）

適合: 1-50 個用戶
```

**部署步驟**:
```bash
# 1. 在 AWS Lightsail 創建 Ubuntu 實例 ($5/月)
# 2. SSH 連接到實例
# 3. 安裝 Docker 和 Docker Compose
# 4. Clone 你的代碼並 docker-compose up
# 就這麼簡單！
```

---

### 方案 2：**無伺服器** - Lambda + API Gateway
```
費用: $1-5/月 (年度 $12-60)
省費: 95% ✅

特點:
✅ 按使用計費（無使用不收費）
✅ 自動擴展
✅ 無需管理伺服器
✅ 高可用性

缺點:
❌ 配置較複雜
❌ 首次啟動慢（冷啟動）
❌ 有請求計費

適合: 非常輕量的使用
```

**成本詳情**:
- Lambda: $0.20 per 100 萬次請求
- API Gateway: $3.50 per 100 萬次請求
- DynamoDB: 按使用計費

如果每月 1,000 個請求:
```
Lambda:      $0.0002
API Gateway: $0.0035
DynamoDB:    $0.0050
────────────
共約: $1-2/月
```

---

### 方案 3：**經濟型** - EC2 t3.nano
```
費用: $3-5/月 (年度 $40-60)
省費: 96% ✅

特點:
✅ 最便宜的 EC2 實例
✅ 足夠處理小流量
✅ 完整的 Linux 環境
✅ 自由度高

缺點:
❌ 需要自己管理
❌ 需要備份自己配置

適合: 技術用戶、開發者
```

**配置**:
```bash
# t3.nano 規格
CPU: 2 vCPU (burstable)
記憶: 0.5 GB
月費: $3-5
```

---

### 方案 4：**簡單方案** - Heroku (非 AWS)
```
費用: $5-7/月 (年度 $60-84)
省費: 93% ✅

特點:
✅ 一鍵部署
✅ 內置資料庫
✅ 自動擴展
✅ 簡單易用

缺點:
❌ 不是 AWS
❌ 依賴第三方

適合: 快速原型、小團隊
```

**部署命令**:
```bash
# 非常簡單
heroku create pcb-bot
git push heroku main
# 就完成了！
```

---

## 💡 我的建議

### 🥇 對你目前的情況（1 個用戶）

**使用 Lightsail** ($5-10/月)

**原因**:
1. ✅ 成本最低（只有現在的 1/11）
2. ✅ 無需配置複雜的架構
3. ✅ 包含資料庫和備份
4. ✅ 足夠支持 100+ 用戶
5. ✅ 隨時可以升級到 ECS

**步驟**:
```bash
# 1. 創建 Lightsail Ubuntu 實例 ($5/月)
# 2. SSH 連接
ssh -i your-key.pem ubuntu@your-instance-ip

# 3. 安裝 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 4. 安裝 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 5. Clone 你的代碼
git clone your-repo.git
cd pcb_line_bot

# 6. 配置環境
cp .env.example .env
# 編輯 .env 添加 LINE Bot 憑證
nano .env

# 7. 啟動應用
docker-compose up -d

# 8. 設置 Nginx 反向代理和 SSL
# (可選，用於 HTTPS)
```

---

## 📈 成長路線圖

```
1 個用戶
    ↓
Lightsail ($5/月)
    ↓
10 個用戶
    ↓
Lightsail ($20/月) 或 升級 EC2
    ↓
100 個用戶
    ↓
EC2 + RDS (成本控制)
    ↓
1,000+ 個用戶
    ↓
ECS Fargate + RDS + ElastiCache (現有方案)
```

---

## 🚀 立即行動（使用 Lightsail）

### 第 1 步：創建 Lightsail 實例

1. 登錄 AWS 控制台
2. 進入 Lightsail
3. 創建 Ubuntu 20.04 實例
4. 選擇 $5/月 方案

### 第 2 步：SSH 連接

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@your-instance-public-ip
```

### 第 3 步：快速安裝腳本

```bash
# 一鍵安裝 Docker + Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh && \
sudo sh get-docker.sh && \
sudo usermod -aG docker ubuntu && \
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose && \
sudo chmod +x /usr/local/bin/docker-compose
```

### 第 4 步：部署應用

```bash
# Clone 代碼
git clone your-repository-url.git
cd pcb_line_bot

# 配置環境
cp .env.example .env
nano .env
# 編輯並保存

# 啟動應用
docker-compose up -d

# 查看日誌
docker-compose logs -f
```

### 第 5 步：配置域名和 HTTPS

```bash
# 安裝 Nginx 和 Let's Encrypt
sudo apt-get update
sudo apt-get install nginx certbot python3-certbot-nginx -y

# 創建 Nginx 配置
sudo nano /etc/nginx/sites-available/pcb-bot

# 添加以下內容：
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# 啟用配置
sudo ln -s /etc/nginx/sites-available/pcb-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 獲取 HTTPS 證書
sudo certbot --nginx -d your-domain.com

# 完成！現在你有 HTTPS 了
```

### 第 6 步：在 LINE Developers 設置 Webhook

```
Webhook URL: https://your-domain.com/callback
```

---

## 💰 詳細成本計算

### Lightsail 方案（推薦）

| 項目 | 月費 | 年費 |
|------|------|------|
| Lightsail 實例 | $5 | $60 |
| 固定 IP | 免費 | 免費 |
| 備份 | 包含 | 包含 |
| 流量 (1TB) | 包含 | 包含 |
| 域名 (可選) | $12/年 | $12 |
| **總計** | **$5** | **$72** |

### vs 企業級方案

```
企業級: $111/月 = $1,330/年
Lightsail: $5/月 = $60/年 (域名除外)

節省: $1,270/年 = 95% ✅
```

---

## ⚠️ 注意事項

### 使用 Lightsail 的限制

✅ 適合 1-100 用戶
❌ 如果達到 1,000+ 用戶，考慮升級

### 數據庫

Lightsail 包含 PostgreSQL 但：
- ✅ 自動備份
- ✅ 可自動擴展
- ❌ 不能像 RDS 那樣完全托管

**解決方案**:
```bash
# 分離資料庫到 RDS ($15/月)
# 或繼續使用 Lightsail 內置 PostgreSQL ($0)
```

---

## 🔄 成長時的升級

### 當達到 10+ 用戶時

```bash
# 升級 Lightsail 實例
# $5/月 → $10/月 → $20/月
# 或升級到 EC2 t3.small ($20/月)
```

### 當達到 100+ 用戶時

```bash
# 考慮分離資料庫到 RDS
# EC2 t3.small ($20) + RDS ($15) = $35/月
# 或升級 Lightsail 高配版本
```

### 當達到 1,000+ 用戶時

```bash
# 回到企業級方案
# ECS Fargate + RDS + ElastiCache
# = $111/月
```

---

## ✅ 最終決定

### 我的建議：**馬上使用 Lightsail**

**為什麼？**
1. ✅ 月費只需 $5（vs $111）
2. ✅ 足夠支持 100+ 用戶
3. ✅ 包含資料庫和自動備份
4. ✅ 隨時可升級到企業級
5. ✅ 不需要複雜的架構

**行動步驟**:
```
1. 登錄 AWS
2. 進入 Lightsail
3. 創建 Ubuntu $5/月 實例
4. 運行上面的安裝腳本
5. 部署應用
6. 更新 LINE Webhook URL
完成！✅
```

---

## 📞 需要幫助？

如果你需要：
1. **Lightsail 部署腳本** - 我可以寫一個自動化腳本
2. **Nginx 配置指南** - 提供完整配置
3. **升級到 ECS 時** - 我們回到原來的方案
4. **其他優化** - 可以進一步調整

就告訴我！

---

**結論**: 使用 Lightsail，年省 $1,270！ 💰

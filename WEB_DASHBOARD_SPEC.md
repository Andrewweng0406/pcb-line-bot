# PCB Quote Bot - Web 管理界面需求文檔

## 項目概述
為 PCB 報價機器人創建 Web 管理界面，讓客戶和內部用戶可以查看、管理、下載報價。

## 頁面設計

### 1. 登入頁面
- 用戶名/郵箱 + 密碼登入
- 或簡單的 API key 認證

### 2. 儀表板首頁
展示統計數據卡片：
- 🔹 總報價數：今日/本月/全部
- 🔹 平均報價額
- 🔹 最近活動時間軸
- 🔹 快捷導航按鈕

### 3. 報價歷史列表頁面
**表格列：**
- 報價編號（PCB-20260526-001）
- 公司名稱
- 層數 (Layer)
- 材料 (Material)
- 尺寸 (Size)
- 數量 (Qty)
- 總價 (Total)
- 狀態 (待審核/已批准/已下單)
- 建立日期
- 操作 (查看/編輯/下載Excel)

**篩選功能：**
- 按日期範圍
- 按層數
- 按材料
- 按公司名
- 按狀態

**搜尋：** 報價編號、公司名稱

### 4. 報價詳情頁面
顯示完整報價資訊：
```
報價編號: PCB-20260526-001
狀態: [待審核 / 已批准 / 已下單]

【客戶信息】
公司名稱: XXX Corp
聯繫方式: (如果有)

【規格信息】
層數: 22L
材料: FR4
尺寸: 700.16 x 565 mm
數量: 3 pcs
投料率: 1.0

【製程】
ENIG: Yes / No
ENIG厚度: 20 u"
VIP: Yes / No
Impedance: Yes / No
背鑽: Yes / No

【計價明細】
面積: 613.17 sq.inch
基礎工程費: 80,000
單位板材費: 65 NT$/in²
板材費: 119,567
額外費用: 5,000
小計: 204,567
折扣: ×0.9
最終價格: 184,110
```

**功能：**
- 編輯報價（價格、狀態、備註）
- 添加內部備註
- 標記狀態（待審核→已批准→已下單）
- 下載 Excel
- 分享給客戶（生成唯讀連結）
- 刪除報價

### 5. 客戶管理頁面
**客戶列表：**
- 公司名
- 聯繫人
- 聯繫電話/郵箱
- 總報價數
- 最後報價日期
- 操作 (查看/編輯/刪除)

**新增客戶表單：**
- 公司名
- 聯繫人
- 電話
- 郵箱
- 常用規格 (JSON)

### 6. 統計報告頁面
- 日期範圍選擇器
- 統計圖表：
  - 報價趨勢線圖 (日/周/月)
  - 按層數分佈柱狀圖
  - 按材料分佈圓餅圖
  - 按狀態分佈
- 下載報告按鈕 (CSV/PDF)

## API 端點需求

應用需要提供以下 REST API：

### 認證
```
POST /api/auth/login
  body: { username, password }
  return: { token, user }
```

### 報價相關
```
GET /api/quotes
  query: { startDate?, endDate?, layer?, material?, status?, search? }
  return: [ { id, quoteNo, companyName, layer, material, size, qty, total, status, createdAt } ]

GET /api/quotes/{id}
  return: { 完整報價信息 }

PATCH /api/quotes/{id}
  body: { total?, status?, notes? }
  return: { 更新後的報價 }

DELETE /api/quotes/{id}
  return: { success }

GET /api/quotes/{id}/download-excel
  return: Excel 檔案

GET /api/quotes/stats/summary
  query: { startDate?, endDate? }
  return: { totalCount, avgPrice, todayCount, etc. }
```

### 客戶相關
```
GET /api/customers
  return: [ { id, name, contact, email, phone, totalQuotes, lastQuoteDate } ]

POST /api/customers
  body: { name, contact, email, phone, commonSpecs }
  return: { 新客戶 }

PATCH /api/customers/{id}
  body: { name?, contact?, email?, phone? }
  return: { 更新後的客戶 }

DELETE /api/customers/{id}
  return: { success }
```

## 技術堆棧建議
- **前端框架：** React / Next.js / Vue
- **UI 組件庫：** shadcn/ui, Tailwind CSS, Material-UI
- **圖表庫：** Chart.js, Recharts
- **表格：** TanStack Table (React Table)
- **日期選擇器：** React DatePicker
- **狀態管理：** React Context / Zustand

## 設計風格
- 現代、簡潔的企業級 UI
- 亮色主題（可選深色模式）
- 響應式設計（移動/平板/桌面）
- 主色：藍色 (#3B82F6)
- 輔助色：綠色（成功）、紅色（危險）、黃色（警告）

## 優先級
1. **MVP（第一版）**
   - 報價列表 + 詳情頁
   - 基本篩選搜尋
   - 下載 Excel
   - 登入頁

2. **V1.1**
   - 客戶管理
   - 編輯功能
   - 狀態管理

3. **V1.2**
   - 統計報告
   - 分享功能
   - 深色模式

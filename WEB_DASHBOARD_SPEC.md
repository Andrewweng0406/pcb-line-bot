# PCB Quote Bot - Web Admin Interface Requirements

## Project Overview
Create a web admin interface for the PCB quote bot so customers and internal users can view, manage, and download quotes.

## Page Design

### 1. Login Page
- Username/email + password login
- Or simple API key authentication

### 2. Dashboard Home
Display statistics cards:
- 🔹 Total quote count: today/this month/all time
- 🔹 Average quote amount
- 🔹 Recent activity timeline
- 🔹 Quick navigation buttons

### 3. Quote History List Page
**Table columns:**
- Quote number (PCB-20260526-001)
- Company name
- Layer
- Material
- Size
- Qty
- Total
- Status (pending review/approved/ordered)
- Created date
- Actions (view/edit/download Excel)

**Filters:**
- By date range
- By layer
- By material
- By company name
- By status

**Search:** Quote number, company name

### 4. Quote Detail Page
Display complete quote information:
```
Quote number: PCB-20260526-001
Status: [Pending review / Approved / Ordered]

[Customer Information]
Company name: XXX Corp
Contact method: (if available)

[Specification Information]
Layer: 22L
Material: FR4
Size: 700.16 x 565 mm
Qty: 3 pcs
Issue ratio: 1.0

[Process]
ENIG: Yes / No
ENIG thickness: 20 u"
VIP: Yes / No
Impedance: Yes / No
Back Drill: Yes / No

[Pricing Details]
Area: 613.17 sq.inch
Base setup fee: 80,000
Unit board charge: 65 NT$/in²
Board charge: 119,567
Extra fees: 5,000
Subtotal: 204,567
Discount: ×0.9
Final price: 184,110
```

**Features:**
- Edit quote (price, status, notes)
- Add internal notes
- Mark status (pending review -> approved -> ordered)
- Download Excel
- Share with customers (generate read-only link)
- Delete quote

### 5. Customer Management Page
**Customer list:**
- Company name
- Contact person
- Contact phone/email
- Total quote count
- Last quote date
- Actions (view/edit/delete)

**New customer form:**
- Company name
- Contact person
- Phone
- Email
- Common specifications (JSON)

### 6. Statistics Report Page
- Date range picker
- Statistics charts:
  - Quote trend line chart (day/week/month)
  - Bar chart by layer distribution
  - Pie chart by material distribution
  - Distribution by status
- Download report button (CSV/PDF)

## API Endpoint Requirements

The app needs to provide the following REST APIs:

### Authentication
```
POST /api/auth/login
  body: { username, password }
  return: { token, user }
```

### Quote-Related
```
GET /api/quotes
  query: { startDate?, endDate?, layer?, material?, status?, search? }
  return: [ { id, quoteNo, companyName, layer, material, size, qty, total, status, createdAt } ]

GET /api/quotes/{id}
  return: { complete quote information }

PATCH /api/quotes/{id}
  body: { total?, status?, notes? }
  return: { updated quote }

DELETE /api/quotes/{id}
  return: { success }

GET /api/quotes/{id}/download-excel
  return: Excel file

GET /api/quotes/stats/summary
  query: { startDate?, endDate? }
  return: { totalCount, avgPrice, todayCount, etc. }
```

### Customer-Related
```
GET /api/customers
  return: [ { id, name, contact, email, phone, totalQuotes, lastQuoteDate } ]

POST /api/customers
  body: { name, contact, email, phone, commonSpecs }
  return: { new customer }

PATCH /api/customers/{id}
  body: { name?, contact?, email?, phone? }
  return: { updated customer }

DELETE /api/customers/{id}
  return: { success }
```

## Recommended Tech Stack
- **Frontend framework:** React / Next.js / Vue
- **UI component library:** shadcn/ui, Tailwind CSS, Material-UI
- **Chart library:** Chart.js, Recharts
- **Tables:** TanStack Table (React Table)
- **Date picker:** React DatePicker
- **State management:** React Context / Zustand

## Design Style
- Modern, clean enterprise UI
- Light theme with optional dark mode
- Responsive design for mobile/tablet/desktop
- Primary color: blue (#3B82F6)
- Supporting colors: green (success), red (danger), yellow (warning)

## Priority
1. **MVP (first version)**
   - Quote list + detail page
   - Basic filtering and search
   - Excel download
   - Login page

2. **V1.1**
   - Customer management
   - Editing features
   - Status management

3. **V1.2**
   - Statistics reports
   - Sharing features
   - Dark mode

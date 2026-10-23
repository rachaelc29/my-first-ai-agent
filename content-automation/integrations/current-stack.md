# 原有基础设施、Drive、Sheets、Make — v4.0 迁移

> 此处为既有配置文档，不代表已实际核对线上资源。包括公开分享权限的操作须先进行隐私与素材许可审查。

# 🛠️ 模塊一：系統基礎設施與工程底座 (One-Off Infrastructure Setup)
*本模塊為系統初始化與工程連線規範，日常文案生成任務可直接跳過此處。*

## 1. Google Drive 目錄樹架構規範
- 📁 `00_Content_Automation_Root/` *(自動化根目錄)*
  - 📁 `01_Raw_Sources/` *(原始採集素材、網頁快照與新聞 PDF)*
  - 📁 `02_Projects_Media_Kit/` *(建案官方原始核心資產包，保持 100% 純淨)*
    - 📁 `[Project_Code]_[Project_Name]/` *(示例：MEL_01_Southbank)*
      - 📁 `Images_HighRes/` *(高清渲染圖、實景圖)*
      - 📁 `Floorplans_Brochures/` *(戶型圖紙、開發商樓書)*
      - 📁 `Branding_Assets/` *(項目專屬 LOGO 與視覺要素)*
  - 📁 `03_Generated_Outputs/` *(交付件歸檔庫)*
    - 📁 `[YYYY-MM]/` *(按年月歸檔)*
  - 📁 `04_System_Templates/` *(Prompt 模版與參考風格庫)*
  - 📁 `05_Media_Temp_Library/` *(媒體臨時加字圖庫，全域公開讀取權限)*

## 2. Google Sheets 數據庫結構字典 (Content_Pipeline)
表頭命名為：`Content_Pipeline`。字段映射規範如下：

| 列名 (Field Name) | 字段代碼 (Key) | 數據類型 | 說明 / 允許枚舉值 (Description & Enum) | 維護方 |
| :--- | :--- | :--- | :--- | :--- |
| **任務ID** | `task_id` | String | 唯一主鍵，如 `TASK_20261023_001` | 系統自動生成 |
| **錄入時間** | `created_at` | DateTime | 初始錄入時間 (YYYY-MM-DD HH:mm) | 系統 / 採集器 |
| **內容類型** | `content_type` | Single Select | `Project_Highlight` / `Market_News` / `Industry_Analysis` | 人工 / 採集器 |
| **建案代碼** | `project_code` | String | 關聯建案唯一代碼（須與 Drive 目錄名嚴格對齊） | 人工 / 採集器 |
| **原始標題** | `source_title` | String | 新聞原標題或本期推介主題 | 人工 / 採集器 |
| **素材鏈接** | `source_url` | URL | 原文網址或對應 Drive 資料夾鏈接 | 人工 / 採集器 |
| **核心事實摘要** | `raw_notes` | Text | 關鍵數據、賣點或政策要點 (AI 輸入源) | 人工 / 提取模塊 |
| **目標受眾** | `tone_target` | Single Select | `Luxury_Investor` / `First_Home_Buyer` / `General_Market` | 人工 / 默認規則 |
| **執行狀態** | `status` | Single Select | `Pending_Generate ➔ Generating ➔ Review_Required ➔ Approved ➔ Publishing ➔ Published ➔ Failed` | 狀態機核心字段 |
| **FB深度長文** | `copy_social` | Long Text | AI 生成：180-240字深度版（含 Hook、正文、CTA、全角標點、防吞空行） | AI 回填 |
| **IG/Threads極簡版** | `copy_short` | Long Text | AI 生成：50-150字真人挖寶感短文（嚴格限 150 字內，帶 #台灣 #香港） | AI 回填 |
| **標籤集合** | `hashtags` | Text | 核心標籤數組，包含 #台灣 #香港 等 | AI 回填 |
| **封面圖 ID** | `drive_image_id` | String | 提權後的封面圖 Drive File ID | AI / 系統回填 |
| **畫廊縮略圖** | `cover_thumbnail` | Formula | 公式 `=IMAGE(generated_cover_url)`，供首屏並排極速審批 | 表格公式自動渲染 |
| **生成封面直鏈** | `generated_cover_url` | URL | 渲染完成的 4:5 封面直鏈 (已提權直接下載流) | AI / 系統回填 |
| **配圖圖集鏈接** | `asset_image_urls` | String/URLs | 輪播圖集直鏈數組（首圖為封面海報，逗號分隔） | AI 匹配 / 人工確認 |
| **計劃發布時間** | `scheduled_publish_time` | DateTime | 預定發布時間戳 | 人工排期 / 自動排期 |
| **實際發布時間** | `published_at` | DateTime | 完成發布的時間戳 | 發布模塊回填 |
| **平台帖子鏈接** | `platform_post_ids` | Long Text | 回寫平台 Post ID 與直達鏈接 JSON (如 `{"FB":"123","IG":"456"}`) | 發布模塊回填 |
| **運行日誌** | `log_message` | Text | 流程異常日誌或 API 報錯信息 | Make 錯誤處理機制 |

## 3. Make.com 算子藍圖與防斷流工程閉環
- **資產提權防 404 (Anti-404 Pipeline)**：
  - 新圖生成上傳 Drive 後，立即調用 Drive API 移入公開臨時庫，並將權限設為 `Role: Reader, Type: Anyone`。
  - 直鏈拼接公式：`https://drive.google.com/uc?export=download&id={{FILE_ID}}` 或讀取 `webContentLink`。
  - 入表前強制自檢權限，非公開鏈接嚴禁入表。
- **三大解耦場景**：
  - **Scenario A（內容生成引擎）**：監聽 `status = Pending_Generate` ➔ 立即更新為 `Generating`（狀態鎖定） ➔ 檢索 Drive 資產 ➔ 調用 LLM API ➔ 解析 JSON ➔ 回填文案並切換為 `Review_Required` ➔ 發送審批提醒。
  - **Scenario B（人工審批）**：用戶在 Google Sheets 畫廊查驗文案與縮略圖，確認通過後一鍵切換為 `Approved` 並排期。
  - **Scenario C（多渠道發射與歸檔）**：每 15 分鐘定時輪詢 `status = Approved` 且時間到期的貼文，按 `Order by: Row number DESC` 自底向上發射，調用 Facebook/Instagram/Threads API 發布，歸檔快照並回寫 `Published` 及平台鏈接。
- **容錯自愈**：API 配置 Break/Resume 重試指令（重試 3 次），失敗寫入 `log_message` 並標記 `Failed`，避免隊列卡死。

---

# VATROC CDM Configuration

本文件說明 VATROC 對 [rpuig2001/CDM](https://github.com/rpuig2001/CDM) EuroScope 插件所使用的設定資料。

目前這份 README 與設定檔存放在 sector files 專案內；建立獨立的 CDM 設定倉庫後，可將本文件作為新倉庫的根目錄 README。

> 本專案僅供 VATSIM 虛擬航空環境使用，不得作為真實世界流量管理或飛航管制依據。

## 專案範圍

本專案負責 VATROC 的 CDM 營運設定，包括：

- `rate.txt`：各機場與跑道配置的基礎離場容量。
- `sidInterval.txt`：特定 SID 組合之間的額外 TTOT 間隔。
- `CDMconfig.xml`：sector files 發布套件所使用的插件選項與遠端資料 URL。

本專案不修改 CDM 插件本身。`CDM.dll`、原始碼、功能與版本發布均由上游專案負責。

## 預定遠端倉庫結構

```text
.
├─ README.md
├─ testing
│  ├─ rate.txt
│  └─ sidInterval.txt
└─ production
   ├─ rate.txt
   └─ sidInterval.txt
```

- 所有變更先進入 `testing`。
- 實際在 EuroScope 驗證後，再將相同內容晉升至 `production`。
- 正式 sector files 只應指向 `production`。
- 使用 Git commit、pull request 與 tag 記錄每次發布，例如 `v1.1`。

## CDMconfig.xml URL

正式環境範例：

```xml
<Rates url="https://raw.githubusercontent.com/OWNER/REPOSITORY/main/production/rate.txt" />
<sidInterval url="https://raw.githubusercontent.com/OWNER/REPOSITORY/main/production/sidInterval.txt" />
```

測試環境將路徑中的 `production` 改為 `testing`。

必須使用能直接回傳純文字內容的 Raw URL，不能使用 GitHub 檔案瀏覽頁網址。倉庫中不得存放 FTP/SFTP 密碼、API key 或其他憑證。

## rate.txt

### 格式

```text
AIRPORT:A:ArrRwyList:NotArrRwyList:D:DepRwyList:NotDepRwyList:DependentRwyList:Rate_RateLvo
```

| 欄位 | 說明 |
| --- | --- |
| `AIRPORT` | 四碼 ICAO 機場代碼 |
| `ArrRwyList` | 必須啟用的到場跑道，逗號分隔；`*` 表示忽略 |
| `NotArrRwyList` | 不應啟用的到場跑道；`*` 表示忽略 |
| `DepRwyList` | 適用的離場跑道，逗號分隔；`*` 表示忽略 |
| `NotDepRwyList` | 不應啟用的離場跑道；`*` 表示忽略 |
| `DependentRwyList` | 使用共同離場序列的相依跑道；`*` 表示忽略 |
| `Rate_RateLvo` | 正常與 LVO 每小時離場架次 |

規則由上而下判斷，第一條符合的規則具有優先權，因此較具體的跑道配置必須放在較前面。

### 目前容量政策

RCTP 桃園機場：

| 運作方式 | Normal | LVO |
| --- | ---: | ---: |
| 平行跑道分流運作 | 30 | 20 |
| 單跑道混合起降 | 20 | 11 |
| 雙跑道相依離場序列 | 25 | 20 |

其他納入 CDM 的單跑道機場，兩個相反跑道方向合併為一條規則，基準為：

- Normal：30 架／小時，平均 2 分鐘一架。
- LVO：20 架／小時，平均 3 分鐘一架。

範例：

```text
RCSS:A:*:*:D:10,28:*:*:30_20
```

跑道清單採明確列舉，不使用離場跑道萬用字元，以避免錯誤或未定義的跑道代碼意外命中。

## sidInterval.txt

### 格式

同一機場、同一跑道的規則使用六欄格式：

```text
AIRPORT,RWY1,SID1,RWY2,SID2,SEPARATION_MINUTES
```

範例：

```text
RCSS,10,APU,10,KUDOS,3
```

SID 欄位填寫 EuroScope 完整 SID 名稱移除最後兩個程序字元後的基礎名稱。例如 `KUDOS1G` 使用 `KUDOS`。

### RCSS 松山機場政策

- 跑道 10 與 28 不會同時開放相反方向的離到場運作。
- 前後機使用相同 SID 時，TTOT 至少間隔 4 分鐘。
- 前後機使用不同 SID、但屬於相同離場方向時，TTOT 至少間隔 3 分鐘。
- 其他 SID 組合不額外處理，維持 `rate.txt` 的基礎容量限制。
- `SPRAY` 為雷達離場，沒有固定導航點，因此不納入 `sidInterval`。

目前離場方向分類：

| 方向 | SID 基礎名稱 |
| --- | --- |
| 北向 | `APU`、`KUDOS`、`PIANO`、`MOLKA`、`ROBIN` |
| 西南向 | `HLG`、`RONEO`、`XEBEC` |
| 東南向 | `YILAN` |

`sidInterval` 只能依機場、兩架航機的跑道及 SID 名稱比對；目前官方插件無法依機型或尾流類別設定不同 SID 間隔。

## 註解格式

兩個檔案均使用獨立的 `#` 註解行：

```text
# Comment
```

為兼顧本地與遠端解析器，請遵守：

- `#` 必須是該行第一個字元。
- 不要在資料行尾端加入註解。
- `rate.txt` 註解中不要使用冒號。
- 資料欄位周圍不要加入多餘空白。

## 載入與更新

- `rate.txt` 可使用本地檔案或 URL。
- 遠端 `rate.txt` 更新後，可在 EuroScope 執行 `.cdm rate` 重新下載。
- `sidInterval` 必須由 URL 啟用；空 URL 代表停用。
- `sidInterval` 目前只在插件初始化時下載，更新後需要重新載入插件或重新啟動 EuroScope。

## 遠端服務故障處理

CDM 在設定 Rate URL 後，不會可靠地自動回退至本地 `rate.txt`。發布套件應繼續保留一份已驗證的本地 Rate 檔案，並準備可將 `<Rates url="" />` 設為空白的緊急備援設定。

若 `sidInterval` URL 無法下載，額外 SID 間隔將無法正常生效；值勤前應確認 URL 可直接開啟並回傳預期內容。

## 修改與驗證清單

修改後至少確認：

1. 跑道編號保留前導零。
2. `rate.txt` 每條資料列均有 9 個冒號分隔欄位。
3. `sidInterval.txt` 每條資料列均有 5 或 6 個逗號分隔欄位。
4. 間隔值為有效的正數，且符合已核定程序。
5. 沒有重複或互相衝突的 SID 配對。
6. RCTP 的具體規則仍位於單跑道機場規則之前。
7. Raw URL 可公開存取，且內容不是 HTML 頁面。
8. 在 testing 環境實際觀察 TTOT 排序後，才同步至 production。

## 上游文件

- [CDM 官方倉庫](https://github.com/rpuig2001/CDM)
- [rate.txt 格式](https://github.com/rpuig2001/CDM#ratetxt)
- [SID Interval 格式](https://github.com/rpuig2001/CDM#sid-interval)
- [CDM Releases](https://github.com/rpuig2001/CDM/releases)

## 授權

CDM 插件及其原始碼適用上游專案的授權。VATROC 自行建立的設定資料若要公開散布，應在獨立設定倉庫建立時一併加入明確的 `LICENSE`。

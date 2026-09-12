# VATROC CDM Configuration

本倉庫集中維護 VATROC 在 [rpuig2001/CDM](https://github.com/rpuig2001/CDM) EuroScope 插件中使用的遠端設定資料。

> 僅供 VATSIM 虛擬航空環境使用，不得作為真實世界流量管理或飛航管制依據。

## 檔案

三個由 CDM 直接讀取的發布檔案維持在根目錄；CI 與檢查器放在支援目錄，不增加 raw URL 的路徑層級：

```text
.
├─ .github/workflows/validate-cdm-data.yml
├─ README.md
├─ rate.txt
├─ scripts/validate_cdm_data.py
├─ taxizones.txt
├─ sidInterval.txt
└─ tests/test_validate_cdm_data.py
```

- `rate.txt`：各機場與跑道配置的基礎離場容量。
- `taxizones.txt`：指定機場及跑道的 taxi time 區域。
- `sidInterval.txt`：特定 SID 組合所需的額外離場間隔。

`CDM.dll`、`CDMconfig.xml`、插件原始碼與版本發布不放在本倉庫；插件本身由上游專案維護，VATROC 的本地部署則位於 [vatroc-es-sectorfiles](https://github.com/GabrielChang906/vatroc-es-sectorfiles)。

## 遠端 URL

sector files 中的 `CDMconfig.xml` 直接讀取下列 raw URL：

- Rate：<https://raw.githubusercontent.com/GabrielChang906/vatroc-es-plugin-cdm/refs/heads/main/rate.txt>
- Taxi zones：<https://raw.githubusercontent.com/GabrielChang906/vatroc-es-plugin-cdm/refs/heads/main/taxizones.txt>
- SID interval：<https://raw.githubusercontent.com/GabrielChang906/vatroc-es-plugin-cdm/refs/heads/main/sidInterval.txt>

對應設定如下：

```xml
<Rates url="https://raw.githubusercontent.com/GabrielChang906/vatroc-es-plugin-cdm/refs/heads/main/rate.txt" />
<Taxizones url="https://raw.githubusercontent.com/GabrielChang906/vatroc-es-plugin-cdm/refs/heads/main/taxizones.txt" />
<sidInterval url="https://raw.githubusercontent.com/GabrielChang906/vatroc-es-plugin-cdm/refs/heads/main/sidInterval.txt" />
<DefaultTaxiTime minutes="10" />
```

因此合併到 `main` 的內容會成為正式資料；修改前應先完成語法檢查，並在 EuroScope 測試環境驗證。

## 自動檢查

每次 push 與 pull request 都會由 GitHub Actions 執行資料驗證。檢查器涵蓋：

- 三個發布檔案是否存在、可用 UTF-8 讀取，且每行欄位數與資料型別正確。
- ICAO、跑道、SID point、容量、時間及座標的基本格式與有效範圍。
- 重複規則、相同條件使用不同數值、跑道同時被要求與排除，以及無法命中的 Rate 規則。
- SID 配對反向重複或間隔衝突。
- Taxi-zone 四邊形的重複點、零面積、自相交及相同區域時間衝突。
- SID 與 taxi-zone 跑道是否有對應的離場 Rate；這類跨檔案疑點只會提出警告，不會阻擋合併。

檢查器不會把目前的容量、SID 分鐘數或 taxi time 寫死，因此調整營運數值本身不會造成失敗。只有格式無法解析或存在明確衝突時，CI 才會以錯誤結束；需要人工確認的項目以警告呈現。

本機可用 Python 3.12 或相容版本執行相同檢查：

```text
python scripts/validate_cdm_data.py --no-annotations
python -m unittest discover -s tests -v
```

## 現行設定原則

### rate.txt

- RCTP 依實際跑道組合分別設定，離場容量採較保守的到場容量概念，以保留運作緩衝。
- 其他民航機場以單跑道運作為基礎，未設定跑道組合差異時使用萬用跑道條件。
- 規則由具體條件到一般條件排列，避免一般規則先行命中而遮蔽較具體的設定。

### sidInterval.txt

目前針對 RCSS：

- 前後機使用相同 SID：至少 4 分鐘。
- 前後機使用不同但同向的 SID：至少 3 分鐘。
- 其他組合不施加額外 SID 間隔。
- SPRAY 系列屬雷達離場，沒有固定離場導航點，因此不列入 SID 分組。

這些 SID 間隔會與 `rate.txt` 的機場／跑道容量限制共同作用；實際 TTOT 取決於插件計算後最嚴格的限制。

### taxizones.txt

未命中 taxi zone 的航機使用 `CDMconfig.xml` 中的 10 分鐘預設值。以下四個機場使用指定時間：

| 機場 | Taxi time |
| --- | ---: |
| RCTP | 20 -> 15 min |
| RCKH | 15 -> 12 min |
| RCSS | 12 -> 10 min |
| RCMQ | 20 分鐘 |

CDM 的 taxi-zone 格式必須包含跑道與四角座標，因此每個機場的各跑道方向分別列出，但同一機場共用涵蓋完整機場地面的矩形與 taxi time。矩形範圍依 sector files 內的跑道及地面資料建立，並保留少量邊界裕度。

## 編輯注意事項

- 每一行只放一條有效規則。
- `rate.txt` 與 `sidInterval.txt` 的註解使用以 `#` 開頭的獨立行，不要把註解接在規則尾端；`taxizones.txt` 保持只有資料行。
- 保留由具體到一般的規則順序。
- 修改 SID 名稱或分組時，應同步核對現行 sector files 與航圖資料。
- 發布前確認三個 raw URL 均回傳純文字，而不是 GitHub HTML 頁面。

## 更新與載入

更新 `main` 後，使用端會在插件重新取得遠端資料時讀到新版本。更新 `rate.txt` 後可依插件支援使用 `.cdm rate` 重新載入；`sidInterval.txt` 若未能即時更新，請重新載入插件或重啟 EuroScope 後再驗證。

遠端檔案不可用時可能影響插件取得設定，正式值勤前應確認網路與 URL 狀態，並保留一份經驗證的本地備份供必要時回復。

## 上游專案

- CDM 插件與格式說明：[rpuig2001/CDM](https://github.com/rpuig2001/CDM)
- VATROC sector files：[GabrielChang906/vatroc-es-sectorfiles](https://github.com/GabrielChang906/vatroc-es-sectorfiles)

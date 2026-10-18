# Final Project Specification: Autonomous Farm OS & Multi-Agent Swarm

## Contents

* **Project Overview**
* **Objectives & Domain Knowledge**
* **Technical Requirements & Tech Stack**
* **System Architecture & Data Models**
* **Tasks & Milestones (100 Points Total)**
  * Task 1: Core Agronomy & Spectral Modeling (15 points)
  * Task 2: Environmental Telemetry & GIS Ingestion (15 points)
  * Task 3: Digital Twin State & Discretization (20 points)
  * Task 4: Specialized Domain Agents (20 points)
  * Task 5: Council Orchestrator & Consensus Protocol (15 points)
  * Task 6: Real-Time API & Interactive Dashboard (15 points)
* **Test Scenarios**
  * Scenario 1: Standard Daylight Cycle & Transpiration
  * Scenario 2: Flash Drought & Water Stress Emergency
  * Scenario 3: Fungal Disease Outbreak & Irrigation Veto
  * Scenario 4: Peak Electricity Tariff Load-Shifting
* **Questions to Answer (`ANSWERS.md`)**
* **Directory Structure & Submission Deliverables**
* **Evaluation Criteria Rubric**
* **Hints & Mathematical Formulas Reference**

---

## 1. Overview

| Field | Value |
| --- | --- |
| **Project Name** | `farm-com` (Autonomous Farm OS) |
| **Role** | Computational Agronomy & AI Systems Engineer |
| **Passing Score** | 70% |
| **Total Points** | 100 |
| **Package Manager** | `uv` (Fastest Python package resolver) |
| **Frameworks** | Python 3.13+, FastAPI, Pydantic V2, NumPy, Open-Meteo, Sentinel-2 STAC |

---

### Description

Bạn được giao nhiệm vụ xây dựng **Autonomous Farm OS**: Một hệ thống kết hợp giữa **Bản sao số (Digital Twin)** và **Hội đồng Đa tác tử AI (Multi-Agent Swarm)** để tự động hóa việc giám sát vi khí hậu, phân tích quang phổ vệ tinh, tính toán thủy nông và ra quyết định canh tác thông minh.

Hệ thống giải quyết bài toán mâu thuẫn điển hình trong nông nghiệp chính xác:
1. **Cây cần nước để phát triển** (Bác sĩ cây trồng & Kỹ sư tưới muốn bơm nước).
2. **Bơm nước vào giờ cao điểm làm tiền điện tăng vọt** (Kinh tế trưởng muốn hoãn bơm).
3. **Độ ẩm đất quá cao kết hợp nhiệt độ cao tạo ổ dịch nấm bệnh Phytophthora** (Bác sĩ cây trồng phải có quyền phủ quyết).
4. **Tổng chỉ huy (Commander)** phải dung hòa các mâu thuẫn này dựa trên dữ liệu định lượng thời gian thực.

---

### Objectives

Sau khi hoàn thành dự án, bạn sẽ làm chủ toàn bộ các kỹ năng:
* **Toán học & Nông học tính toán:** Cài đặt thuật toán viễn thám ($NDVI, NDWI$) và phương trình bốc thoát nước chuẩn quốc tế **FAO-56 Penman-Monteith**.
* **Xử lý dữ liệu Địa lý Không gian (GIS):** Kéo và xử lý các dải quang phổ (B4, B8, B11) của vệ tinh **Sentinel-2**.
* **Mô phỏng Digital Twin:** Thiết kế State Machine dạng lưới ma trận ô đất ($N \times M$), quản lý chu trình tiêu hao và nạp ẩm tầng rễ theo bước thời gian (Tick Engine).
* **Kiến trúc Multi-Agent Swarm:** Thiết kế các Agent có vai trò chuyên biệt, giao tiếp qua schema JSON có cấu trúc (Pydantic), và tranh luận (Debate & Consensus) thay vì dùng 1 LLM duy nhất.
* **Hạ tầng Real-time Fullstack:** Sử dụng FastAPI, WebSocket truyền dữ liệu trực tiếp lên Dashboard tương tác 2.5D.

---

## 2. Mock Data Models & Schemas

### 1. PlotZone Model (Từng luống đất trong Digital Twin)

| Field | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | `str` | Format `Z_{x}_{y}` | Mã định danh luống đất |
| `x`, `y` | `int` | $\ge 0$ | Tọa độ trên ma trận trang trại |
| `crop_type` | `str` | Enum / String | Loại cây (Dâu tây, Cà phê Arabica, v.v.) |
| `growth_stage` | `str` | `seedling`, `vegetative`, `flowering`, `fruiting`, `harvest_ready` | Giai đoạn phát triển |
| `soil_moisture_pct` | `float` | $0.0 \le \text{val} \le 100.0$ | Độ ẩm tầng rễ (%) |
| `soil_ph` | `float` | $4.0 \le \text{val} \le 8.5$ | Độ pH của đất |
| `ndvi` | `float` | $-1.0 \le \text{val} \le 1.0$ | Chỉ số diệp lục tán lá |
| `ndwi` | `float` | $-1.0 \le \text{val} \le 1.0$ | Chỉ số hàm lượng nước trong lá |
| `health_status` | `str` | `healthy`, `water_stressed`, `pathogen_risk`, `recovering` | Tình trạng cây trồng |

### 2. WeatherTelemetry Model (Vi khí hậu thời gian thực)

| Field | Type | Unit | Description |
| --- | --- | --- | --- |
| `temp_c` | `float` | °C | Nhiệt độ không khí hiện tại |
| `temp_max`, `temp_min` | `float` | °C | Nhiệt độ cao nhất / thấp nhất trong ngày |
| `humidity_percent` | `float` | % | Độ ẩm tương đối |
| `wind_speed_ms` | `float` | m/s | Tốc độ gió ở độ cao 2m ($u_2$) |
| `solar_radiation_mj` | `float` | $\text{MJ}/m^2/\text{day}$ | Tổng bức xạ sóng ngắn mặt trời ($R_s$) |
| `precipitation_mm` | `float` | mm | Lượng mưa thực tế |

---

## 3. Tasks & Milestones (100 Điểm)

### Task 1: Core Agronomy & Spectral Modeling (15 điểm)
**Thời gian ước tính:** 60 phút  
Xây dựng module thuần túy tính toán vật lý & quang phổ (Pure functions, không phụ thuộc I/O ngoại vi).

**Yêu cầu:**
1. **Quang phổ viễn thám (`core/spectral.py`):**
   - Viết hàm `compute_ndvi(nir, red)`: $(NIR - Red) / (NIR + Red)$.
   - Viết hàm `compute_ndwi(nir, swir)`: $(NIR - SWIR) / (NIR + SWIR)$.
   - Viết hàm `compute_evi(nir, red, blue)`: Xử lý hiệu ứng nền đất và khí quyển.
   - Bắt buộc xử lý edge-cases: Mẫu số = 0, giá trị reflectance âm, giới hạn $[-1.0, 1.0]$.
2. **Mô hình bốc thoát hơi nước FAO-56 Penman-Monteith (`core/agronomy_models.py`):**
   - Tính áp suất khí quyển $P$, hằng số tâm lý kế $\gamma$, độ dốc áp suất hơi bão hòa $\Delta$, bức xạ thuần $R_n$.
   - Tính lượng bốc thoát nước chuẩn $ET_0$ (mm/ngày).
   - Tính nhu cầu nước thực tế $ET_c = ET_0 \times K_c$ và thâm hụt nước tầng rễ (Root Zone Deficit).
3. **Độ ngày sinh trưởng (GDD):**
   - Tính $GDD = \max(0, \frac{T_{max} + T_{min}}{2} - T_{base})$ với nhiệt độ cắt trần $T_{cutoff}$.

**Deliverables:**
* `backend/core/spectral.py`
* `backend/core/agronomy_models.py`
* `tests/test_agronomy.py` (Unit tests kiểm tra công thức với dataset mẫu của FAO).

---

### Task 2: Environmental Telemetry & GIS Ingestion (15 điểm)
**Thời gian ước tính:** 60 phút  
Xây dựng tầng nạp dữ liệu ngoại vi bất đồng bộ (Async Ingestion Layer).

**Yêu cầu:**
1. **Client thời tiết Open-Meteo (`ingestion/weather_client.py`):**
   - Viết async client gọi endpoint API mở của Open-Meteo theo tọa độ GPS.
   - Trích xuất: `temperature_2m`, `relative_humidity_2m`, `precipitation`, `wind_speed_10m`, `shortwave_radiation_sum`.
   - Cơ chế fallback: Nếu mất mạng, trả về dữ liệu vi khí hậu mô phỏng chân thực theo mùa.
2. **Client ảnh vệ tinh Sentinel-2 (`ingestion/satellite_client.py`):**
   - Interface chuẩn kết nối Copernicus STAC API để lấy dữ liệu các band B2 (Blue), B4 (Red), B8 (NIR), B11 (SWIR).
   - Cung cấp chế độ Mock Synthesizer giả lập phổ phản xạ thực tế để dev mượt mà khi offline.
3. **Bộ giả lập cảm biến đất IoT (`ingestion/sensor_sim.py`):**
   - Mô phỏng tốc độ bốc hơi nước của đất dựa trên $ET_0$ và lượng mưa.
   - Bổ sung nhiễu Gaussian Noise ($\mu=0, \sigma=0.5$) để giả lập rung sai cảm biến phần cứng thật.

**Deliverables:**
* `backend/ingestion/weather_client.py`
* `backend/ingestion/satellite_client.py`
* `backend/ingestion/sensor_sim.py`
* `tests/test_ingestion.py`

---

### Task 3: Digital Twin State & Discretization (20 điểm)
**Thời gian ước tính:** 75 phút  
Xây dựng mô hình Bản sao số (Digital Twin) quản lý trạng thái nông trại dạng ma trận.

**Yêu cầu:**
1. **Spatial State Grid (`core/twin_state.py`):**
   - Khởi tạo ma trận $4 \times 4$ ô đất (`PlotZone`), gán cây trồng đa dạng (Dâu tây, Cà phê, Ớt chuông, Cẩm tú cầu).
   - Lưu trữ lịch sử hành động bất biến (`ActionLog`): thời gian, agent đề xuất, lượng nước tưới, lý do.
2. **Tick Engine - Bước thời gian:**
   - Viết hàm `advance_simulation(hours, rain_mm)`:
     - Giảm độ ẩm tầng rễ theo số giờ trôi qua.
     - Tăng độ ẩm nếu có mưa hoặc có lệnh tưới.
     - Cập nhật trạng thái `health_status` khi các chỉ số vượt ngưỡng an toàn.

**Deliverables:**
* `backend/core/twin_state.py`
* `tests/test_twin_state.py`

---

### Task 4: Specialized Domain Agents (20 điểm)
**Thời gian ước tính:** 90 phút  
Triển khai các AI Agent chuyên môn hóa với góc nhìn phản biện độc lập.

**Yêu cầu:**
1. **Định nghĩa Base Agent & Structured Output Schema (`agents/base_agent.py`):**
   - Schema `AgentOpinion`: `agent_id`, `role`, `confidence` (0.0-1.0), `recommendation`, `urgency` (`low`, `medium`, `critical`), `data_points`, `reasoning`.
2. **Agronomist Agent (`agents/agronomist.py`):**
   - Đọc chỉ số NDVI/NDWI của từng luống.
   - Phát hiện luống cây có sinh khối thấp ($NDVI < 0.45$) hoặc tán lá thiếu nước ($NDWI < 0.12$).
   - Cảnh báo rủi ro bùng phát nấm khi độ ẩm đất $> 80\%$ kết hợp nhiệt độ $> 26^\circ\text{C}$.
3. **Irrigation Engineer Agent (`agents/irrigation.py`):**
   - Đọc kết quả tính toán $ET_0$ và độ ẩm đất hiện tại.
   - Tính thể tích nước cần tưới (mm) cho từng van nhỏ giọt.
4. **Market & Economics Agent (`agents/market.py`):**
   - Phân tích biểu giá điện (Giờ cao điểm: 09:30-11:30 & 17:00-20:00 vs Giờ thấp điểm: 22:00-04:00).
   - Khuyến nghị hoãn bơm nước vào giờ cao điểm nếu độ ẩm đất chưa chạm ngưỡng nguy hiểm ($> 45\%$).
   - Đọc giá nông sản để ưu tiên các luống cây sắp đến kỳ thu hoạch có biên lợi nhuận cao nhất.

**Deliverables:**
* `backend/agents/base_agent.py`
* `backend/agents/agronomist.py`
* `backend/agents/irrigation.py`
* `backend/agents/market.py`
* `tests/test_agents.py`

---

### Task 5: Council Orchestrator & Consensus Protocol (15 điểm)
**Thời gian ước tính:** 60 phút  
Xây dựng cơ chế hòa giải và ban hành Nghị quyết canh tác (Consensus & Execution).

**Yêu cầu:**
1. **Commander Agent (`agents/commander.py`):**
   - Thu thập toàn bộ `AgentOpinion` từ 3 chuyên gia.
   - Áp dụng ma trận giải quyết mâu thuẫn:
     - *Quy tắc an toàn sinh học:* Nếu Bác sĩ cảnh báo nguy cơ nấm bệnh, cấm tuyệt đối lệnh tưới bất kể Kỹ sư tưới yêu cầu.
     - *Quy tắc tối ưu chi phí:* Nếu đang giờ điện cao điểm, chỉ cho phép tưới các luống đang trong tình trạng hạn hán nguy cấp (độ ẩm $< 35\%$). Các luống khác hoãn lại đến giờ thấp điểm.
   - Tạo ra danh sách hành động thực thi (`scheduled_actions`): mã van, thời lượng bơm (phút), lưu lượng (mm).
   - Cập nhật trực tiếp kết quả vào Bản sao số Digital Twin.

**Deliverables:**
* `backend/agents/commander.py`
* `tests/test_commander.py`

---

### Task 6: Real-Time API & Interactive Dashboard (15 điểm)
**Thời gian ước tính:** 60 phút  
Xây dựng API RESTful, kênh WebSocket và giao diện Dashboard điều hành.

**Yêu cầu:**
1. **FastAPI Routes (`api/` & `main.py`):**
   - `GET /api/farm/state`: Trả về toàn bộ trạng thái ma trận đất và vi khí hậu.
   - `POST /api/farm/tick`: Tua thời gian mô phỏng.
   - `POST /api/agents/convene`: Kích hoạt phiên họp Hội đồng Agent.
   - `WS /ws/telemetry`: WebSocket stream dữ liệu thời gian thực.
2. **Giao diện Dashboard trực quan (`backend/static/index.html`):**
   - Hiển thị ma trận 16 ô đất với màu sắc cảnh báo theo thời gian thực.
   - Hiển thị các chỉ số vi khí hậu và giá trị bốc thoát nước $ET_0$.
   - Khung Deliberation hiển thị từng phát biểu và độ tin cậy của từng Agent.

**Deliverables:**
* `backend/main.py`
* `backend/api/routes_farm.py`
* `backend/api/routes_agents.py`
* `backend/static/index.html`

---

## 4. Test Scenarios (Kịch Bản Kiểm Thử)

### Scenario 1: Chu Trình Ngày Nắng Tiêu Chuẩn (Standard Daylight Flow)
* **Điều kiện:** Trời nắng 26°C, độ ẩm 60%, bức xạ 19 MJ, độ ẩm đất giảm xuống 58%.
* **Diễn biến:**
  * Kỹ sư Thủy nông phát hiện độ ẩm dưới 70%, đề xuất tưới 12mm.
  * Kinh tế trưởng xác nhận đang trong khung giờ điện bình thường.
  * Bác sĩ cây trồng xác nhận lá cây khỏe mạnh (NDVI = 0.72).
  * $\rightarrow$ **Commander phê duyệt lệnh tưới nhỏ giọt bình thường.**

### Scenario 2: Cắt Hạn Khẩn Cấp (Flash Drought Emergency)
* **Điều kiện:** Ô `Z_2_1` có độ ẩm tụt xuống 32% (nguy kịch), đúng vào khung **Giờ cao điểm tiền điện**.
* **Diễn biến:**
  * Kinh tế trưởng cảnh báo tiền điện đắt gấp 2.5 lần.
  * Kỹ sư Thủy nông nhấn mạnh cây sẽ héo vĩnh viễn nếu không tưới ngay.
  * $\rightarrow$ **Commander ra lệnh ghi đè (Override):** Ưu tiên sinh tồn của cây, kích hoạt van tưới khẩn cấp cho riêng ô `Z_2_1` trong 15 phút.

### Scenario 3: Cảnh Báo Nấm Bệnh & Phủ Quyết Tưới (Fungal Pathogen Veto)
* **Điều kiện:** Ô `Z_1_2` có độ ẩm 85% sau mưa, nhiệt độ không khí 28°C oi bức. Kỹ sư tưới theo lịch định kỳ muốn bơm thêm nước.
* **Diễn biến:**
  * Bác sĩ cây trồng cảnh báo nguy cơ thối rễ nấm *Phytophthora* (Urgency: Critical).
  * $\rightarrow$ **Commander thực thi quyền phủ quyết (Veto):** Hủy toàn bộ lệnh tưới, đề xuất bật quạt thông gió hoặc điều động drone phun thuốc sinh học.

---

## 5. Câu Hỏi Ôn Tập Chuyên Sâu (`ANSWERS.md`)

Bạn sẽ tự trả lời 5 câu hỏi này vào file `ANSWERS.md` để đào sâu kiến thức:
1. **Nông học tính toán:** Tại sao phương trình **FAO-56 Penman-Monteith** lại chính xác hơn nhiều so với các công thức bốc thoát hơi nước đơn giản chỉ dựa vào nhiệt độ (như Thornthwaite hay Hargreaves)?
2. **Viễn thám:** Tại sao chỉ số NDVI không đủ để phát hiện hạn hán sớm, mà bắt buộc phải kết hợp thêm chỉ số NDWI (dải SWIR)?
3. **Kiến trúc Multi-Agent:** Tại sao việc chia nhỏ thành các Agent có mục tiêu đối lập (Chăm cây vs Tiết kiệm chi phí) lại giúp hệ thống ra quyết định tốt hơn nhiều so với việc đưa tất cả dữ liệu vào 1 prompt của 1 LLM duy nhất?
4. **Bản sao số (Digital Twin):** Khi ảnh vệ tinh chỉ chụp lại trang trại 5 ngày/lần, làm thế nào để Digital Twin duy trì độ chính xác của chỉ số NDVI theo từng giờ? (Gợi ý: Kalman Filter hoặc Data Interpolation).
5. **Triển khai Thực tế (Production):** Để đưa hệ thống này ra một nông trại 100 hecta thực tế với chi phí thấp nhất, bạn sẽ thiết kế kiến trúc phần cứng cảm biến (LoRaWAN, ESP32) và tối ưu băng thông như thế nào?

---

## 6. Tiêu Chí Đánh Giá (Rubric 100 Điểm)

| Tiêu Chí | Điểm | Xuất Sắc (100%) | Đạt (75%) | Cần Cải Thiện (50%) |
| --- | --- | --- | --- | --- |
| **Lõi Nông Học (Task 1)** | 15 | Tính đúng $ET_0$ Penman-Monteith, NDVI, NDWI, có unit test FAO chuẩn | Tính đúng công thức nhưng thiếu unit test trường hợp biên | Công thức sai hoặc thiếu các hằng số vật lý |
| **Nạp Dữ Liệu & GIS (Task 2)** | 15 | Gọi Async Open-Meteo mượt mà, có retry, mock Sentinel chuẩn xác | Kéo được thời tiết nhưng xử lý lỗi mạng còn sơ sài | Chỉ có dữ liệu tĩnh cứng (hard-coded) |
| **Bản Sao Số (Task 3)** | 20 | Ma trận ô đất quản lý trạng thái mượt mà, tick simulation phản ánh đúng vật lý | Trạng thái lưới hoạt động nhưng chưa có nhật ký bất biến | Lưới đất không tự cập nhật theo bước thời gian |
| **Đa Tác Tử Chuyên Môn (Task 4)** | 20 | Cả 3 Agent có góc nhìn phản biện rõ ràng, structured output chuẩn Pydantic | Agent hoạt động nhưng logic phân tích còn đơn giản | Agent chỉ trả về text tự do, không parse được JSON |
| **Hội Đồng & Đồng Thuận (Task 5)** | 15 | Xử lý mâu thuẫn chặt chẽ (luật nấm bệnh, luật giờ điện cao điểm) | Tổng hợp được ý kiến nhưng chưa có logic giải quyết xung đột | Commander chỉ nối chuỗi các ý kiến của Agent |
| **API & Giao Diện (Task 6)** | 15 | Dashboard trực quan, WebSocket chạy thời gian thực, nút tương tác mượt mà | Giao diện hiển thị được dữ liệu nhưng chưa có WebSocket | Chỉ có API thô, không có giao diện xem |
| **Tổng Cộng** | **100** | | | |

---

## 7. Gợi Ý & Công Thức Toán Học (Hints & Formulas)

> [!TIP]
> **Phương Trình FAO-56 Penman-Monteith:**
> $$ET_0 = \frac{0.408 \Delta (R_n - G) + \gamma \frac{900}{T + 273} u_2 (e_s - e_a)}{\Delta + \gamma (1 + 0.34 u_2)}$$
> * Trong tính toán bước ngày, nhiệt lượng đất $G \approx 0$.
> * Áp suất hơi bão hòa: $e_s = 0.6108 \exp\left(\frac{17.27 T}{T + 237.3}\right)$.
> * Áp suất hơi thực tế: $e_a = e_s \times \frac{RH}{100}$.

> [!TIP]
> **Công Thức Quang Phổ Sentinel-2:**
> * $\text{NDVI} = \frac{B8 - B4}{B8 + B4}$ (B8 là NIR 842nm, B4 là Red 665nm).
> * $\text{NDWI} = \frac{B8 - B11}{B8 + B11}$ (B11 là SWIR 1610nm, hấp thụ rất mạnh bởi nước trong tế bào lá).

> [!TIP]
> **Cấu Trúc Quản Lý Gói Bằng `uv`:**
> * Chạy test: `uv run pytest tests/`
> * Kiểm tra linting: `uv run ruff check .`
> * Chạy server: `uv run python main.py`

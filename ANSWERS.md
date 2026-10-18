# Chuyên Đề Nghiên Cứu & Trả Lời Câu Hỏi (ANSWERS.md)
**Dự án:** `farm-com` - Autonomous Farm OS & Multi-Agent Swarm  
**Học viên / Kỹ sư:** [Họ và tên của bạn]

---

### Câu 1: Nông Học Tính Toán (Computational Agronomy)
> **Câu hỏi:** Tại sao phương trình **FAO-56 Penman-Monteith** lại chính xác hơn nhiều so với các công thức bốc thoát hơi nước đơn giản chỉ dựa vào nhiệt độ (như Thornthwaite hay Hargreaves)? Hãy giải thích vai trò của bức xạ thuần ($R_n$), tốc độ gió ($u_2$) và độ ẩm thiếu hụt ($e_s - e_a$).

**Trả lời:**
*(Gợi ý: Phân tích về cân bằng năng lượng bề mặt và động lực học khuếch tán hơi nước của lớp khí quyển sát mặt đất...)*

---

### Câu 2: Viễn Thám & Quang Phổ (Remote Sensing)
> **Câu hỏi:** Tại sao chỉ số NDVI không đủ để phát hiện hạn hán sớm, mà bắt buộc phải kết hợp thêm chỉ số NDWI (dải Shortwave Infrared - SWIR)? Khi cây bị thiếu nước trong 24-48 giờ đầu, tế bào lá phản ứng như thế nào trước khi chất diệp lục bị phá hủy?

**Trả lời:**
*(Gợi ý: Cơ chế suy giảm hàm lượng nước trong mô xốp lá cây trước khi lục lạp bị thoái hóa...)*

---

### Câu 3: Kiến Trúc Multi-Agent Swarm (Agentic AI)
> **Câu hỏi:** Tại sao việc chia nhỏ thành các Agent có mục tiêu đối lập (Chăm sóc cây vs Tiết kiệm chi phí vs Phòng ngừa dịch bệnh) lại giúp hệ thống ra quyết định tốt hơn nhiều so với việc đưa tất cả dữ liệu vào 1 prompt của 1 LLM duy nhất?

**Trả lời:**
*(Gợi ý: Giảm thiểu hiện tượng Hallucination, phân chia trách nhiệm - Separation of Concerns, và cơ chế cân bằng kiểm tra chéo - Checks and Balances...)*

---

### Câu 4: Đồng Bộ Bản Sao Số (Digital Twin Synchronization)
> **Câu hỏi:** Khi ảnh vệ tinh Sentinel-2 chỉ bay qua trang trại 5 ngày/lần, làm thế nào để Digital Twin duy trì độ chính xác của chỉ số NDVI theo từng giờ? Hãy đề xuất một giải pháp kỹ thuật (ví dụ: Kalman Filter, nội suy suy giảm theo thời gian, hoặc kết hợp camera Edge VLM cục bộ).

**Trả lời:**
*(Gợi ý: Phương pháp Data Assimilation kết hợp giữa mô hình suy đoán và dữ liệu đo đạc thực tế định kỳ...)*

---

### Câu 5: Triển Khai Thực Tế & Tối Ưu Chi Phí (Production & Edge Computing)
> **Câu hỏi:** Để triển khai hệ thống này trên một nông trại 100 hecta ngoài thực địa với chi phí tối thiểu, bạn sẽ thiết kế hạ tầng IoT cảm biến (LoRaWAN, Zigbee, ESP32) và chính sách gửi dữ liệu (Telemetry cadence) như thế nào để vừa tiết kiệm pin mặt trời vừa đảm bảo dữ liệu cho AI?

**Trả lời:**
*(Gợi ý: Giao thức mạng diện rộng công suất thấp LoRaWAN, kiến trúc Edge Gateway gửi dữ liệu theo sự kiện - Event-triggered thay vì polling liên tục...)*

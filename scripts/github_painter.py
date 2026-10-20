#!/usr/bin/env python3
"""
GitHub Contribution Graph Painter & Streak Farm Tool
Tự động tạo lịch sử commit về quá khứ (backdate) để phủ xanh GitHub profile.
"""

import os
import sys
import subprocess
import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

# Đảm bảo in UTF-8 không lỗi trên Windows Console (cp1252 / cp437)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def get_git_config(key: str) -> str:
    """Lấy cấu hình git hiện tại (name/email)"""
    try:
        result = subprocess.run(
            ["git", "config", key],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception:
        return ""


def run_cmd(cmd: list[str], cwd: Path, env: dict = None) -> subprocess.CompletedProcess:
    """Chạy command an toàn"""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=True
    )


def generate_commits(
    target_dir: Path,
    days: int = 365,
    min_commits: int = 1,
    max_commits: int = 5,
    frequency: float = 0.85,
    weekend_factor: float = 0.4,
    user_name: str = "",
    user_email: str = "",
    allow_empty: bool = False,
    dry_run: bool = False
):
    """Tạo các commits theo lịch sử ngày giờ ngẫu nhiên"""
    target_dir = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📂 Thư mục repo mục tiêu: {target_dir}")
    print(f"👤 Git User Name: {user_name}")
    print(f"📧 Git User Email: {user_email}")
    print(f"📅 Số ngày quét ngược về quá khứ: {days} ngày")
    print(f"🎲 Tỷ lệ ngày có commit: {int(frequency * 100)}%")
    print(f"📊 Số commit mỗi ngày: {min_commits} - {max_commits}")

    if not dry_run:
        # 1. Khởi tạo Git repo nếu chưa có
        git_dir = target_dir / ".git"
        if not git_dir.exists():
            print("\n⚙️ Đang khởi tạo git repository mới...")
            run_cmd(["git", "init", "-b", "main"], cwd=target_dir)
        else:
            print("\n⚙️ Phát hiện git repository có sẵn. Sử dụng repo này...")

        # Cấu hình user.name và user.email cho repo mục tiêu
        if user_name:
            run_cmd(["git", "config", "user.name", user_name], cwd=target_dir)
        if user_email:
            run_cmd(["git", "config", "user.email", user_email], cwd=target_dir)

        # Tạo file README ban đầu nếu chưa có
        readme_file = target_dir / "README.md"
        if not readme_file.exists():
            with open(readme_file, "w", encoding="utf-8") as f:
                f.write("# Daily Activity Vault\n\nAutomated workspace tracking and streak logs.\n")
            run_cmd(["git", "add", "README.md"], cwd=target_dir)
            try:
                run_cmd(["git", "commit", "-m", "Initial commit"], cwd=target_dir)
            except subprocess.CalledProcessError:
                pass

    log_file = target_dir / "activity.log"
    today = datetime.now()
    total_commits = 0
    active_days = 0

    base_env = os.environ.copy()

    for day_offset in range(days, -1, -1):
        target_date = today - timedelta(days=day_offset)
        is_weekend = target_date.weekday() >= 5  # 5: Thứ 7, 6: Chủ nhật

        # Điều chỉnh xác suất commit theo cuối tuần
        prob = frequency * (weekend_factor if is_weekend else 1.0)
        if random.random() > prob:
            continue

        # Số lượng commit ngẫu nhiên trong ngày
        daily_count = random.randint(min_commits, max_commits)
        if is_weekend:
            daily_count = max(1, daily_count // 2)

        active_days += 1

        for c_idx in range(daily_count):
            # Chọn giờ ngẫu nhiên trong khung giờ làm việc: 8h00 - 22h59
            hour = random.randint(8, 22)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)

            commit_dt = target_date.replace(hour=hour, minute=minute, second=second)
            # Format ISO 8601: 2026-05-14T15:20:30
            date_str = commit_dt.strftime("%Y-%m-%dT%H:%M:%S")

            if dry_run:
                total_commits += 1
                continue

            env = base_env.copy()
            env["GIT_AUTHOR_DATE"] = date_str
            env["GIT_COMMITTER_DATE"] = date_str

            if allow_empty:
                cmd = [
                    "git", "commit", "--allow-empty",
                    "--date", date_str,
                    "-m", f"chore(activity): sync log entry [{date_str}]"
                ]
                run_cmd(cmd, cwd=target_dir, env=env)
            else:
                # Ghi 1 dòng vào file activity.log
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{date_str}] auto sync entry #{c_idx + 1}\n")

                run_cmd(["git", "add", "activity.log"], cwd=target_dir)
                cmd = [
                    "git", "commit",
                    "--date", date_str,
                    "-m", f"chore(activity): sync log entry [{date_str}]"
                ]
                run_cmd(cmd, cwd=target_dir, env=env)

            total_commits += 1

        # Hiển thị tiến trình mỗi 30 ngày
        if day_offset % 30 == 0 or day_offset == 0:
            pct = int(((days - day_offset) / days) * 100) if days > 0 else 100
            print(f"⏳ Tiến độ: {pct}% (Đã tạo {total_commits} commits cho {active_days} ngày...)")

    print("\n" + "=" * 60)
    print("🎉 HOÀN TẤT QUÁ TRÌNH TẠO COMMITS!")
    print(f"📊 Tổng số ngày có commit: {active_days} / {days + 1} ngày")
    print(f"🚀 Tổng số commit đã tạo: {total_commits} commits")
    print("=" * 60)

    if not dry_run:
        print("\n👉 CÁC BƯỚC TIẾP THEO ĐỂ ĐƯA LÊN GITHUB:")
        print("1. Mở GitHub và tạo một repository MỚI:")
        print("   - Tên repo gợi ý: streak-vault (hoặc tuỳ bạn đặt)")
        print("   - Chọn: [x] Private (Khuyên dùng để giữ kín và bảo mật)")
        print("   - KHÔNG tích chọn 'Add a README file'")
        print("2. Chạy 2 lệnh sau trong thư mục repo vừa tạo:")
        print(f"   cd \"{target_dir}\"")
        print("   git remote add origin https://github.com/<tai-khoan-github>/<ten-repo>.git")
        print("   git branch -M main")
        print("   git push -u origin main")
        print("\n3. BẬT HIỂN THỊ Ô XANH PRIVATE TRÊN GITHUB PROFILE:")
        print("   - Vào trang Profile GitHub cá nhân của bạn.")
        print("   - Ở góc phải trên bảng ô xanh (Contributions), bấm 'Contribution settings'.")
        print("   - Tích chọn: 'Private contributions'.")
        print("   - F5 tải lại trang, bạn sẽ thấy toàn bộ ô xanh sáng rực!")
        print("\n💡 MẸO: Nếu sau này không muốn giữ những ô xanh này nữa, bạn chỉ cần")
        print("   vào GitHub Settings của repo đó và bấm XÓA REPO là xong 100% sạch sẽ!")


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Contribution Graph Painter & Streak Farm Tool"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="../github-streak-farm",
        help="Đường dẫn thư mục repo mục tiêu (Mặc định: ../github-streak-farm)"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=365,
        help="Số ngày muốn phủ ngược về quá khứ (Mặc định: 365)"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["natural", "full"],
        default="natural",
        help="'natural': Trông tự nhiên có ngày nghỉ (~85% ngày), 'full': Phủ kín 100% tất cả các ngày"
    )
    parser.add_argument(
        "--min-commits",
        type=int,
        default=1,
        help="Số commit tối thiểu mỗi ngày (Mặc định: 1)"
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=5,
        help="Số commit tối đa mỗi ngày (Mặc định: 5)"
    )
    parser.add_argument(
        "--email",
        type=str,
        default="",
        help="Email GitHub (nếu để trống sẽ tự lấy từ git config user.email)"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="",
        help="Tên GitHub (nếu để trống sẽ tự lấy từ git config user.name)"
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Dùng git --allow-empty thay vì ghi file activity.log"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chạy thử xem trước số liệu, không tạo commit thật"
    )

    args = parser.parse_args()

    # Tự động lấy user.name / user.email nếu chưa truyền
    user_name = args.name or get_git_config("user.name") or "Your Name"
    user_email = args.email or get_git_config("user.email")

    if not user_email:
        print("⚠️ Cảnh báo: Không tìm thấy git config user.email.")
        user_email = input("Vui lòng nhập Email GitHub của bạn: ").strip()

    frequency = 1.0 if args.mode == "full" else 0.85
    weekend_factor = 0.9 if args.mode == "full" else 0.35

    target_path = Path(args.output_dir)

    generate_commits(
        target_dir=target_path,
        days=args.days,
        min_commits=args.min_commits,
        max_commits=args.max_commits,
        frequency=frequency,
        weekend_factor=weekend_factor,
        user_name=user_name,
        user_email=user_email,
        allow_empty=args.allow_empty,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()

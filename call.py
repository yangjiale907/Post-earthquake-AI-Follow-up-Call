#!/usr/bin/env python3
"""
拨打电话 — SIM7600 4G HAT via USB AT port.

硬件连接：
  SIM7600 4G HAT 插在树莓派（或同类 Linux 板）的 GPIO 排针上，
  USB 线连到板子的 USB 口。模块上电后，Linux 会枚举出多个 ttyUSB 设备，
  其中 ttyUSB2 用于发送 AT 命令（电话、短信、网络等）。

AT 命令简述：
  AT          — 握手/存活检测，正常返回 OK
  ATD<号>;    — 拨号（分号 = 语音呼叫，无分号 = 数据呼叫）
  ATH          — 挂断当前通话
"""

import sys
import time
import serial

# --------------------------------------------------
# 硬件串口配置
# --------------------------------------------------
PORT = "/dev/ttyUSB2"      # SIM7600 的 AT 命令端口（不是 ttyUSB0/ttyUSB1）
BAUD = 115200              # 模块默认波特率
TIMEOUT = 3                # 串口读取超时（秒）

# --------------------------------------------------
# 默认拨出号码（命令行传参会覆盖）
# --------------------------------------------------
PHONE = "19334630455"


# ============================================================
# send_at — 所有与模块交互的底层入口
# ============================================================
def send_at(ser: serial.Serial, cmd: str, wait: float = 1) -> list[str]:
    """
    发送一条 AT 命令，等待模块返回，然后把非空响应行收集成列表返回。

    参数
    ----
    ser  : 已打开的 serial.Serial 对象
    cmd  : AT 命令字符串，不含末尾的 \\r\\n（函数会自动补上）
    wait : 发送后等待的秒数，给模块处理时间。默认 1 秒；
            拨号等耗时较长的命令需加大，比如 ATD 用 6 秒。

    返回
    ----
    list[str] — 模块返回的每一行（去除了空白和 \\r\\n），按顺序排列。
                典型情况：["ATDxxxx;", "", "OK"]
                如果没有响应就是空列表。
    """
    # 发送命令（AT 协议要求以 \\r\\n 结尾）
    ser.write((cmd + "\r\n").encode())

    # 等待模块处理完
    time.sleep(wait)

    # 把缓冲区里的所有响应行读出来
    lines: list[str] = []
    while ser.in_waiting:                         # 缓冲区里还有数据可读
        raw: bytes = ser.readline()               # 读到 \\n 为止
        try:
            line = raw.decode(errors="ignore").strip()  # 转成字符串，丢弃非法字节
        except Exception:
            continue                               # 极端异常时跳过这行（几乎不会触发）
        if line:                                   # 忽略空行
            lines.append(line)
    return lines


# ============================================================
# main — 主流程：打开串口 → 检测模块 → 拨号 → 等待 → 挂断
# ============================================================
def main() -> None:
    # ---- 确定拨出号码：优先命令行参数，没有则用默认值 ----
    phone = sys.argv[1] if len(sys.argv) > 1 else PHONE

    # ---- 打开串口 ----
    try:
        ser = serial.Serial(PORT, BAUD, timeout=TIMEOUT)
    except serial.SerialException as e:
        # 常见原因：端口不存在、没插 USB 线、被其他程序占用、
        #          用户不在 dialout 组所以没权限
        print(f"无法打开串口 {PORT}: {e}")
        sys.exit(1)

    print(f"串口 {PORT} 已打开，检测模块...")

    # ---- 发送 AT 握手命令，确认模块在线 ----
    resp = send_at(ser, "AT")
    if not resp or resp[-1] != "OK":
        # 可能原因：
        #   - 模块没上电（HAT 的电源跳线帽没接）
        #   - PWRKEY 没拉低触发开机
        #   - SIM 卡没插或没插好
        #   - ttyUSB2 不是 AT 命令端口（试试 ttyUSB0/ttyUSB1）
        print("模块未响应，请检查 SIM7600 供电、天线、SIM 卡")
        ser.close()
        sys.exit(1)
    print("模块就绪")

    # ---- 拨号 ----
    # ATD 命令末尾的分号 ";" 表示语音呼叫。
    # 去掉分号 = 数据呼叫（PPP 拨号），这里我们是语音通话，必须加分号。
    print(f"正在拨打 {phone}...")
    resp = send_at(ser, f"ATD{phone};", wait=6)
    print("ATD 响应:", resp)

    # ---- 等待 5 秒让对方电话响一会儿 ----
    print("通话中，5 秒后自动挂断...")
    time.sleep(5)

    # ---- 挂断 ----
    resp = send_at(ser, "ATH")
    print("挂断响应:", resp)

    # ---- 收尾 ----
    ser.close()
    print("完成")


if __name__ == "__main__":
    main()

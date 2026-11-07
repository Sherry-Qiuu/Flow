# H07 · CSI 摄像头

> **时长** 45 分钟　**难度** ★★☆　**前置** H02
> 这一节让设备能"看见"课程表和作业本 —— 也是整个产品最能出彩的演示点。

---

## 1. 这一节做完你会得到什么

- 树莓派能拍照、能预览、能存图
- 一段封装好的取帧代码（给软件的"拍照导入待办"用）
- 一套固定的拍摄参数（距离、补光、分辨率）

---

## 2. 先认识两种排线（别插错）

你手上有两种"扁平排线"，**长得像但完全不同**：

| 排线 | 针数 | 用途 | 能不能接摄像头 |
|---|---|---|---|
| 摄像头自带排线 | **22 针**（Pi 5 专用） | 接 CSI 摄像头 | ✅ 只能用它 |
| FPC 软排线（自购） | 12 针 | 接其它模组 | ❌ **完全不能用** |

> 采购清单里那根 `0.5mm 12P 10cm` **不是给摄像头的**。Pi 5 用的是 22 针、0.5mm 间距的排线，摄像头包装里已经带了。**不要试图把 12P 那根塞进摄像头接口**，针脚对不上会顶坏触点。

---

## 3. 树莓派 5 的摄像头接口在哪

树莓派 5 有两组 **MIPI 排线接口**，都在板的短边上，标着：

- **CAM0 / CAM1**（接摄像头）
- **DISP0 / DISP1**（接显示屏）

> Pi 5 的排线接口和 Pi 4 **不一样**：Pi 4 是窄的 15 针，Pi 5 是宽的 22 针。所以买摄像头时必须买"含 Pi 5 FPC"的版本 —— 你买的那款是对的。

**接线位置**：接 **CAM0**（靠近 USB 口的那个接口）。

---

## 4. 插排线（最容易出错的一步）

### 4.1 断电

**先 `sudo shutdown -h now`，等绿灯不闪了再拔电源。带电插排线会烧摄像头。**

### 4.2 打开卡扣

Pi 5 的 FPC 接口是**下压式（翻盖式）**：

1. 用指甲或塑料撬棒，把黑色/白色的**卡扣向上翻开**（约 90°）。
2. 打开后能看到一排金属触点。

### 4.3 插入排线

**关键：排线的金属触点（金手指）朝向板子内侧**，也就是朝向 USB 口的方向；蓝色加强片朝外。

- 插到底，**看不到金手指为止**（差不多插进去 5mm）。
- 排线要**插正**，不能一边深一边浅。
- 插好后把卡扣**按回去**，要听到/感觉到"咔"的一声。

### 4.4 摄像头那一端

摄像头小板上的接口通常是**掀开式（ZIF）**：

1. 把黑色卡扣往上掀。
2. 排线**金手指朝下**（朝向 PCB）插入。
3. 压下卡扣。

> ⚠️ 两端的金手指朝向**可能不一样**。判断原则：金手指永远朝向板子上有触点的那个面。不确定就查摄像头模块的印刷图示 —— 或者先插一端、上电测，不行再翻面（**但要断电再翻**）。

---

## 5. 验证（10 分钟）

```bash
# 1. 看有没有被识别
rpicam-hello --list-cameras
```

正常输出：

```
Available cameras
-----------------
0 : imx219 [3280x2464 10-bit RGGB] (/base/soc/i2c0mux/i2c@1/imx219@10)
    Modes: 'SRGGB10_CSI2P' : 1640x1232 [60.00 fps - (0, 0)/3280x2464 crop]
           ...
```

```bash
# 2. 预览 5 秒（需要接显示器）
rpicam-hello --timeout 5000

# 3. 拍一张照片
rpicam-still -o ~/flow/data/test.jpg --width 1920 --height 1080 --timeout 2000
```

```bash
# 4. 看文件
ls -lh ~/flow/data/test.jpg
```

文件大小应该在 **200KB–1MB** 之间。太小（<30KB）说明画面全黑/全白。

### 5.1 如果没有 `rpicam-` 命令

说明系统不是 Bookworm，或者摄像头没启用：

```bash
which rpicam-still
# 没有输出说明命令不存在

# 老系统用这个：
which libcamera-still
```

如果两个都没有，重装 Bookworm 64-bit 系统。

---

## 6. 拍照参数怎么调（15 分钟）

产品里"拍课程表/作业本"这个场景，比拍风景苛刻得多：**文字要能看清**。

### 6.1 推荐参数

```bash
rpicam-still \
  -o ~/flow/data/doc.jpg \
  --width 3280 --height 2464 \
  --timeout 1500 \
  --shutter 20000 \
  --analoggain 1.5 \
  --awbgains 1.2,1.6 \
  --nopreview
```

| 参数 | 作用 | 为什么这么设 |
|---|---|---|
| `--width/--height 3280x2464` | 用满 800 万像素 | 文字识别需要分辨率 |
| `--shutter 20000` | 快门 20ms | 室内光下不糊，又不至于拖影 |
| `--analoggain 1.5` | 增益 | 室内偏暗时提亮，太高会有噪点 |
| `--awbgains` | 白平衡 | 避免纸张拍成黄色 |
| `--nopreview` | 不弹预览窗 | 无头模式必须加 |

### 6.2 拍摄距离

IMX219 是**定焦镜头**（对焦固定在无限远附近），最佳清晰距离：

| 目标 | 距离 |
|---|---|
| A4 纸上的作业 | **25–35 cm** |
| 电脑屏幕上的课表 | 30–40 cm |
| 远处的黑板 | 1 m 以上（会偏模糊） |
| **小于 10 cm** | 一定会糊 |

> 这是定焦镜头的物理限制，不是软件能救的。产品设计上要引导用户"把纸放 30cm 处"，可以在屏幕上显示一个取景框提示。

### 6.3 补光

室内照明不足时，识别率会暴跌。三个办法：

1. 在产品外壳上加一圈**暖白 LED 补光**（H01 里买的导光柱就是干这个的）。
2. 用户自己开台灯。
3. 软件层面：拍完先判断亮度，太暗就提示"请开灯或靠近光源"。

---

## 7. 封装成代码（15 分钟）

`~/flow/code/camera.py`（直接给软件侧 HAL 用）：

```python
#!/usr/bin/env python3
"""心流 FLOW · 摄像头模块"""
import subprocess
import tempfile
import os
from pathlib import Path

DATA_DIR = Path.home() / "flow" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class CameraError(Exception):
    pass


def capture(path: str | None = None,
            width: int = 3280,
            height: int = 2464,
            timeout_ms: int = 1500,
            shutter_us: int = 20000,
            gain: float = 1.5) -> str:
    """拍一张照片，返回文件路径。失败抛 CameraError。"""
    if path is None:
        path = str(DATA_DIR / "capture.jpg")

    cmd = [
        "rpicam-still",
        "-o", path,
        "--width", str(width),
        "--height", str(height),
        "--timeout", str(timeout_ms),
        "--shutter", str(shutter_us),
        "--analoggain", str(gain),
        "--nopreview",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise CameraError(r.stderr.strip() or "rpicam-still 失败")
    if not os.path.exists(path) or os.path.getsize(path) < 20000:
        raise CameraError("拍到的文件异常小，可能镜头被遮挡")
    return path


def probe() -> bool:
    """检查摄像头是否可用"""
    try:
        r = subprocess.run(["rpicam-hello", "--list-cameras"],
                           capture_output=True, text=True)
        return "imx219" in r.stdout or "0 :" in r.stdout
    except FileNotFoundError:
        return False


def capture_thumbnail(path: str, out: str, size: int = 400) -> str:
    """生成缩略图，用于屏幕显示确认"""
    subprocess.run(["rpicam-still", "--nopreview"], capture_output=True)  # 忽略
    try:
        from PIL import Image
        im = Image.open(path)
        im.thumbnail((size, size))
        im.save(out)
        return out
    except ImportError:
        return path


if __name__ == "__main__":
    print("摄像头可用:", probe())
    p = capture()
    print("已保存:", p, f"({os.path.getsize(p)/1024:.0f} KB)")
```

运行：

```bash
cd ~/flow/code
sudo apt install -y python3-pil     # 缩略图要用
python3 camera.py
```

---

## 8. 安装到外壳

- 前面板开一个**直径 8–10mm 的圆孔**对准镜头，孔边倒角防刮。
- 摄像头 PCB 用 **3M VHB 胶**贴在前面板内侧，位置对准孔中心。
- **镜头面和面板之间留 1–2mm**，不要贴死（贴合会进灰、还会让画面出现压痕）。
- 排线要**留 15% 余量**并绕开铰链，**绝对不能压在铰链转轴上**（第一次开合就断）。
- 排线拐弯处不要死折，走大弧。

> ⚠️ 排线是所有件里最容易被扯断的。装配时先用胶带把排线固定在底板上，再合壳。

---

## 9. 验证清单

- [ ] `rpicam-hello --list-cameras` 列出 `imx219`
- [ ] `rpicam-still` 能生成 >200KB 的 jpg
- [ ] 照片清晰，文字可辨认
- [ ] 30cm 距离拍 A4 纸，文字边缘锐利
- [ ] 装进外壳后仍能正常拍照
- [ ] 开合支架 10 次，排线没松

---

## 10. 排错

| 现象 | 原因 | 处理 |
|---|---|---|
| `No cameras available` | 排线没插到底 / 卡扣没压 | 断电重插，确认金手指朝向 |
| `No cameras available` | 排线插反了 | 断电，翻转排线重插 |
| `No cameras available` | 接的是 DISP 口 | 换到 **CAM0** |
| 照片全黑 | 镜头盖没摘 / 光圈被挡 / 快门太短 | 检查镜头，延长 `--shutter` |
| 照片全白过曝 | 曝光太长 | 减 `--shutter` |
| 照片模糊 | 距离太近（<10cm） | 移到 30cm |
| 照片颜色发黄/发蓝 | 白平衡 | 调 `--awbgains` 或加 `--awb auto` |
| 报 `failed to acquire camera` | 有别的进程占用了摄像头 | `ps aux \| grep rpicam` 杀掉 |
| 拍照时树莓派重启 | 供电不足 | 回 H03 查电压 |
| 排线插几次后接触不良 | 金手指磨损 | 换一根排线（你买了 2 个摄像头，有备用） |

---

## 11. 记录表

| 项目 | 结果 |
|---|---|
| 摄像头型号 / 识别名 | ______ |
| 接的接口 | CAM0 / CAM1 |
| 默认最大分辨率 | ______ |
| 拍一张 3280×2464 的文件大小 | ______ KB |
| 拍 A4 纸的最佳距离 | ______ cm |
| 用的快门 / 增益 | ______ / ______ |
| 排线长度够不够 | 够 / 差 ______ cm |

---

## 12. 下一节

[H08 · 无线充电模块](H08-无线充电模块.md) —— 手机放上支架就开始充电。

> 如果无线充暂时不想做（它是 P1），可以直接跳到 [H09 显示屏与外壳装配](H09-显示屏与外壳装配.md)。

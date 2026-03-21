# 端到端 Demo 测试报告 #1：手动 Prompt 模式

> 测试日期：2026-03-22
> 测试脚本：`scripts/demo_e2e.py`（手动 prompt 模式）
> ComfyUI 版本：v0.9.2（秋叶整合包 v3）
> 硬件：NVIDIA GeForce RTX 5090 Laptop GPU, 24GB VRAM
> 固定参数：seed=42

## 测试目的

验证 P2-10 端到端 demo 脚本的完整流程，评估"Canny 边缘图 + 手动 prompt → Z-Image-Turbo + ControlNet Union 还原"方案的还原质量和压缩效率。

## 测试图片

6 张越野车/自驾场景图片，涵盖不同地形和光照条件：


| #   | 文件名                   | 场景                  | 原图尺寸      |
| --- | --------------------- | ------------------- | --------- |
| 1   | `canyon_jeep.jpg`     | 峡谷碎石路，深色越野车穿行于陡峭岩壁间 | 1152x2048 |
| 2   | `rock_climbing.jpeg`  | 黄色越野车攀爬岩石坡，低角度仰拍    | 1151x2048 |
| 3   | `jungle_trail.jpg`    | 绿色越野车行驶在丛林泥土小路上     | 1536x2048 |
| 4   | `forest_snow.jpg`     | 绿色吉姆尼行驶在雪地松林碎石路上    | 1365x2048 |
| 5   | `mountain_road.jpg`   | 黑色皮卡行驶在山间公路上        | 1152x2048 |
| 6   | `prairie_highway.jpg` | 草原公路延伸向雪山，路上有牛群     | 1152x2048 |


图片存放位置：`resources/test_images/`

## 手动 Prompt


| #   | Prompt                                                                                                                                                            |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | A dark off-road vehicle driving through a narrow rocky canyon with steep cliff walls, dusty gravel road, arid mountain landscape under hazy sky                   |
| 2   | A yellow off-road truck climbing over large rocks on a steep hillside trail, low angle view, green trees and blue sky in background, adventurous atmosphere       |
| 3   | A dark green SUV driving along a muddy dirt trail surrounded by lush tropical vegetation, misty mountains in the distance, overcast sky, rear view                |
| 4   | A green Suzuki Jimny driving on a rocky mountain trail flanked by tall pine trees, patches of snow on the ground, bright sunny day, rear view                     |
| 5   | A dark pickup truck driving on a curved mountain highway with road markings, power transmission towers, green mountain slopes, cloudy sky                         |
| 6   | A straight asphalt road stretching toward snow-capped mountains, cows walking on the road, vast green grassland on both sides, white clouds and mist around peaks |


## 传输统计


| #   | 场景   | 原图大小      | 边缘图大小     | Prompt 大小 | 传输总量      | 压缩比    | 发送端耗时 | 接收端耗时 | 总耗时   |
| --- | ---- | --------- | --------- | --------- | --------- | ------ | ----- | ----- | ----- |
| 1   | 峡谷越野 | 235,820 B | 305,963 B | 143 B     | 306,106 B | 0.77x  | 1.3s  | 59.7s | 61.0s |
| 2   | 攀岩越野 | 46,225 B  | 169,693 B | 155 B     | 169,848 B | 0.27x  | 3.1s  | 50.8s | 54.0s |
| 3   | 丛林小路 | 226,516 B | 255,195 B | 146 B     | 255,341 B | 0.89x  | 3.1s  | 65.1s | 68.2s |
| 4   | 雪地松林 | 918,506 B | 430,058 B | 141 B     | 430,199 B | 2.14x  | 3.2s  | 62.1s | 65.3s |
| 5   | 山间公路 | 842,569 B | 74,843 B  | 137 B     | 74,980 B  | 11.24x | 3.2s  | 51.9s | 55.1s |
| 6   | 草原雪山 | 302,866 B | 82,808 B  | 161 B     | 82,969 B  | 3.65x  | 2.4s  | 51.2s | 53.6s |


**统计摘要**：

- 平均压缩比：3.16x（中位数 1.52x）
- 平均发送端耗时：2.7s
- 平均接收端耗时：56.8s
- 3/6 张图的压缩比 < 1（边缘图 PNG 比原图 JPEG 还大）

## 逐张评价

### #1 峡谷越野 — 良好

- **结构保持**：岩壁轮廓、碎石路面、车辆位置精准还原
- **语义还原**：整体"干燥荒凉"氛围一致；颜色略偏冷灰（原图偏暖黄）
- **视觉质量**：车辆形态清晰可辨，岩石纹理自然
- 输出目录：`output/demo/01_canyon_jeep/`

### #2 攀岩越野 — 良好

- **结构保持**：车身形态和攀爬姿态通过边缘图精准传递
- **语义还原**：车辆黄色准确还原；背景绿树更鲜艳、天空更蓝（色彩风格有差异但视觉效果反而更好）
- **视觉质量**：原图 46KB 高压缩 JPEG，还原图画质反而更清晰
- 输出目录：`output/demo/02_rock_climbing/`

### #3 丛林小路 — 优秀

- **结构保持**：车辆形态、绿植层次、远山云雾高度还原
- **语义还原**：泥土小路颜色和质感准确；整体氛围（潮湿、热带、阴天）与原图高度一致
- **视觉质量**：6 张中最佳还原效果之一
- 输出目录：`output/demo/03_jungle_trail/`

### #4 雪地松林 — 良好

- **结构保持**：松树、雪地、车辆三者结构清晰还原
- **语义还原**：车身颜色从深绿偏向浅绿（prompt "green" 被模型解读为亮绿）；雪地和岩石分布准确
- **视觉质量**：光照感（晴天强光）还原到位
- 输出目录：`output/demo/04_forest_snow/`

### #5 山间公路 — 良好（有幻觉）

- **结构保持**：公路标线、车辆、山坡轮廓还原准确
- **语义还原**：边缘图信息较稀疏（大面积纯黑），模型主要依赖 prompt 补充语义
- **视觉质量**：远处出现了原图没有的小房子——模型在边缘信息不足区域产生了**幻觉**
- **压缩比最高**（11.24x）：边缘简单（大面积天空和山体梯度平滑）
- 输出目录：`output/demo/05_mountain_road/`

### #6 草原雪山 — 优秀

- **结构保持**：公路线条、雪山轮廓、草甸、牛群位置全部准确
- **语义还原**：道路标线（黄色中线）颜色和位置精准；云雾缭绕的雪山氛围高度还原
- **视觉质量**：6 张中最佳还原效果；整体色调偏冷（原图偏暖绿），但场景识别度极高
- 输出目录：`output/demo/06_prairie_highway/`

## 综合评价

### 1. 结构保持度：优秀（5/5）

Canny 边缘图有效约束了还原图的整体构图。6 张图的车辆位置、道路走向、地形轮廓全部精准保持，未出现结构性错位。

### 2. 语义还原度：良好（4/5）

手动 prompt 能有效传递场景核心语义（车辆颜色、地形类型、天气氛围）。但存在细节偏差：车身具体颜色会有色偏（深绿→浅绿），边缘稀疏区域偶有幻觉（#5 的小房子）。

### 3. 视觉质量：良好（4/5）

还原图画质整体清晰自然，无明显 AI 生成伪影（无扭曲、无马赛克）。Z-Image-Turbo 在 2048px 分辨率下表现稳定。部分图片色调会偏移（偏冷或偏暖），不影响场景识别。

### 4. 场景适应性：良好（4/5）

- **最佳场景**：构图简洁、边缘清晰的（#6 草原公路、#3 丛林小路）
- **良好场景**：纹理丰富但结构明确的（#1 峡谷、#2 攀岩、#4 雪地）
- **一般场景**：边缘稀疏、大面积平滑区域的（#5 山间公路——边缘图黑色区域过多，模型缺少约束）

### 5. 压缩效率：需改进（2/5）

- 3/6 张图的压缩比 < 1（边缘图 PNG 编码后比原图 JPEG 还大）
- 核心问题：Canny 边缘图使用 PNG 无损编码，而原图是高压缩率 JPEG
- 当前 2048px 的边缘图分辨率过高，传输效率低

### 6. 耗时：符合预期（3/5）

- 发送端（Canny 提取）稳定 1.3-3.2s
- 接收端（图像生成）50-65s，主要瓶颈在扩散模型推理
- 总耗时 53-68s/张，暂不适合实时传输，但作为原型验证可接受

## 关键发现

1. **端到端流程完全打通**——demo 脚本运行稳定，6 张不同场景全部成功
2. **Canny 边缘 + prompt 语义传输方案可行**——结构保持是核心优势，prompt 补充颜色/材质/氛围
3. **压缩效率是最大短板**——需要优化边缘图编码（降分辨率、换格式），否则传输数据量反而更大
4. **手动 prompt 质量直接影响还原效果**——后续 VLM 自动生成 prompt（P2-13）至关重要
5. **边缘信息稀疏时模型容易产生幻觉**——场景越简单，边缘约束越弱，需要 prompt 更精确

## 改进方向

1. **边缘图压缩**：降低传输分辨率（如 512px）、使用 JPEG 编码、或探索更紧凑的条件表示
2. **VLM 自动 prompt**：替代手动 prompt，提高描述精度和一致性（P2-13）
3. **多条件融合**：增加深度图条件（Depth Map），减少边缘稀疏区域的幻觉
4. **色彩校正**：可通过传输低分辨率颜色参考图（如 32x32 缩略图）来约束色调


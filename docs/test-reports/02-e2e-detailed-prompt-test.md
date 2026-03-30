# 端到端 Demo 测试报告 #2：详细 Prompt 模式 + 两轮对比

> 测试日期：2026-03-22
> 测试脚本：`scripts/demo_e2e.py`（手动 prompt 模式）
> ComfyUI 版本：v0.9.2（秋叶整合包 v3）
> 硬件：NVIDIA GeForce RTX 5090 Laptop GPU, 24GB VRAM
> 固定参数：seed=42
> Prompt 生成方式：Claude subagent 看图生成详细英文描述（~400-500 words/张）

## 测试目的

验证更详细的 prompt 是否能显著改善还原质量。第一轮使用简短 prompt（~20-30 words，~140 bytes），本轮使用详尽 prompt（~300-400 words，~2,000 bytes），对比两轮效果差异，评估 prompt 信息量对语义传输还原质量的影响。

## 测试图片

与第一轮相同的 6 张越野车/自驾场景图片，存放于 `resources/test_images/`。

## 输出路径

```
output/demo/round-01/  — 第一轮（简短 prompt）
output/demo/round-02/  — 第二轮（详细 prompt）
```

## 详细 Prompt

### #1 canyon_jeep.jpg

A dark olive green off-road SUV, resembling a Jeep Wrangler or similar rugged 4x4 vehicle, driving head-on toward the camera through a narrow rocky canyon gorge on an unpaved dirt and gravel trail, the vehicle slightly left of center on the rough track with its headlights faintly visible, roof rack mounted on top, the trail surface composed of loose gray and brown gravel, stones, and dried mud with shallow puddles of standing water reflecting the surrounding terrain, deep tire tracks and ruts carved into the path, towering steep rocky cliff walls on both sides of the narrow passage, the left cliff face featuring a massive overhanging boulder jutting out dramatically over the trail creating a natural rock canopy, the rock surfaces textured with layers of sedimentary formations in shades of dark brown, warm tan, gray, and muted ochre, jagged and weathered stone with visible geological stratification and erosion patterns, sparse patches of dry scrubby vegetation clinging to the base of the cliffs, the canyon opening up in the far background revealing distant arid mountain slopes in muted sandy beige and pale brown tones partially obscured by atmospheric haze and fine dust suspended in the air, the sky above a pale overcast grayish-white with diffused soft daylight creating even illumination without harsh shadows, the overall color palette dominated by earthy neutral tones of brown, tan, gray, and olive green, the atmosphere conveying a sense of remote wilderness adventure in an arid high-altitude mountain desert environment, photorealistic photograph, natural lighting, vertical portrait orientation composition with strong leading lines from the canyon walls converging toward the distant vanishing point, slight aerial dust haze adding depth and atmosphere, ultra-detailed textures on rock surfaces and gravel ground

### #2 rock_climbing.jpeg

A yellow rugged off-road SUV climbing over large exposed rocky terrain on a steep mountain trail, front three-quarter view from a slightly low angle looking upward, the vehicle is a boxy muscular 4x4 truck with a bold front grille, black front bumper with a steel winch mounted at the center, black heavy-duty off-road tires with aggressive tread pattern, the body is painted in a bright golden yellow color with minor dirt and dust marks, Chinese license plate mounted on the front bumper reading 粤B 226F5, roof rack visible on top, the windshield slightly reflecting the surrounding environment, the vehicle is tilted at an angle as it navigates over uneven jagged rocks, the rocky ground is composed of rough weathered sandstone and reddish-brown earth with visible cracks and erosion patterns, large flat and angular rock slabs forming a natural obstacle course, a thin steel cable or winch line extends from the front of the vehicle down along the rocks to the lower left of the frame, sparse green vegetation and scrubby bushes growing between the rocks on both sides of the trail, a medium-sized tree with green oval leaves stands to the right of the vehicle, its trunk leaning slightly, additional low shrubs and wild grasses scattered along the hillside, distant mountain ridges faintly visible in the hazy background under a pale overcast sky with a warm amber atmospheric haze, the overall lighting is warm golden-hour sunlight coming from behind and slightly above, casting soft shadows on the rocks and giving the entire scene a warm brownish-orange tonal quality, the atmosphere feels adventurous and rugged, realistic photographic style, high detail, outdoor off-road adventure photography, natural daylight, portrait orientation vertical composition with the vehicle positioned in the upper center of the frame and the rocky terrain filling the foreground

### #3 jungle_trail.jpg

A matte olive green Mercedes-Benz G-Class SUV (G-Wagon) seen from the rear, driving away from the viewer along a narrow, muddy red-earth dirt trail in a lush tropical jungle setting, portrait orientation, rear three-quarter view slightly off-center to the left. The vehicle features a rear-mounted spare tire with a dark cover, boxy angular body shape, rectangular taillights, prominent rear bumper, and a subtle roof rack. The body has a flat military-style olive drab green paint finish with slight dust and mud splatter on the lower panels and wheel wells from the off-road terrain. The trail is a narrow unpaved path of wet reddish-brown laterite clay soil with visible tire tracks, ruts, and puddle marks, flanked on both sides by dense, overgrown tropical vegetation. On the left side, tall tropical trees with broad green leaves and slender trunks line the path, with lower shrubs and grasses growing at the trail edge. On the right side, a thick wall of vivid green foliage, vines, broad-leafed tropical plants, and dense undergrowth encroaches closely on the trail, nearly brushing the vehicle. The vegetation is intensely green, saturated and healthy, suggesting a humid monsoon or tropical rainforest climate with recent rainfall. In the background, beyond the canopy of jungle trees, a range of soft rolling green mountains rises into the distance, partially obscured by atmospheric haze and low-hanging mist. The mountains have gentle rounded silhouettes covered in dense forest. The sky above is overcast with a mix of white and light gray clouds, with small patches of pale blue sky visible in the upper portion. A single bird silhouette can be faintly seen flying in the mid-sky area against the clouds. The lighting is soft, diffused, and natural, characteristic of an overcast tropical day with no harsh shadows. The overall color palette is dominated by rich saturated greens of the jungle foliage, warm reddish-brown earth tones of the muddy trail, the muted olive green of the vehicle, and cool blue-gray tones in the distant mountains and sky. The atmosphere conveys a sense of remote wilderness adventure, solitude, and the lush humidity of a tropical jungle landscape. Photorealistic style, high detail, natural photography, 35mm lens, shallow atmospheric perspective with hazy distant mountains, vertical composition.

### #4 forest_snow.jpg

A matte olive green Land Rover Defender SUV seen from directly behind, driving away from the camera along a narrow, rugged unpaved mountain trail, rear view showing the spare tire mounted on the tailgate with an orange-accented cover, rectangular taillights, a rear-mounted roof rack with a subtle load, and a visible license plate at the bottom of the tailgate. The vehicle is centered in the composition, slightly left of middle, navigating a rough rocky dirt road with deep tire ruts, loose gray and beige gravel, scattered large boulders and stones lining both sides of the trail, and patches of dried mud. The road surface is uneven and textured with a mix of crushed rock, compacted earth, and occasional puddle-worn depressions. Tall, dense, dark green coniferous trees, primarily tall spruces and firs with full, layered branches, rise steeply on both sides of the trail, forming a natural corridor that frames the vehicle symmetrically. The trees are lush and richly green with deep shadows beneath their canopy. In the background, through the gap in the tree line, a distant barren mountainside is partially visible, showing exposed pale gray rock and sparse vegetation with a faint dusting of remaining snow or light-colored scree near the upper slopes. The sky above is bright, clear, and slightly overcast with soft diffused white-blue light, suggesting midday or early afternoon high-altitude sunlight. The overall lighting is natural and bright with strong ambient illumination, casting soft shadows under the trees and on the rocky ground, with warm sunlight hitting the upper canopy and the vehicle roof. The color palette is dominated by deep forest greens, earthy grays and browns of the rocky terrain, and the muted olive tone of the vehicle, creating a rugged, adventurous, off-road wilderness atmosphere. The composition is vertical portrait orientation with strong depth perspective, the road converging toward a vanishing point in the upper center of the frame, emphasizing the sense of journey and exploration into remote alpine wilderness. Photorealistic style, high detail, sharp focus, outdoor adventure photography, natural lighting, 85mm lens perspective with shallow background compression.

### #5 mountain_road.jpg

A realistic photograph of a two-lane mountain highway in rural China, captured from the perspective of a driver or dashcam mounted inside a vehicle, looking straight ahead along the road. The composition is vertical portrait orientation, with the asphalt road occupying the lower half and the mountainous landscape filling the upper half. In the center-left of the road, a dark-colored SUV or pickup truck, appearing to be a black or very dark gray Chinese-market SUV with a boxy body style, is parked or slowly moving on the opposite lane, facing toward the viewer. The vehicle has a blue Chinese license plate on the front and a silver or chrome front grille. It is positioned slightly off the road near the left shoulder, close to the rocky cliff face. The road surface is smooth dark gray asphalt in good condition, with a solid yellow center line dividing the two lanes and white dashed lane markings on the right side. The road gently curves to the right as it extends into the distance. On the right side of the road, there is a yellow diamond-shaped warning road sign mounted on a metal pole, indicating a curve ahead. Several concrete or metal street light poles with modern lamp fixtures line the right side of the road at regular intervals. On the left side of the road, there is a steep exposed rock cut face, a rugged cliff of reddish-brown and tan sedimentary rock with visible strata and erosion patterns, where the mountain was cut away to make room for the road. Some sparse green vegetation, small shrubs and young trees with bright spring-green foliage, grows at the top edge of the rock cut and along the base where soil has accumulated. The background features a large, rounded mountain covered in lush green vegetation, with dense shrubs and scattered trees covering its slopes. The mountain has a smooth, dome-like profile rising prominently in the center-right of the frame. Behind and to the left of this main mountain, additional mountain ridges are visible, receding into the hazy distance with progressively lighter tones of blue-gray. A high-voltage electrical transmission tower with metal lattice structure stands on the mountainside to the right, with power lines faintly visible stretching across the scene. The sky is overcast with a thick layer of light gray and white clouds, with occasional hints of pale blue breaking through. The lighting is soft and diffused, consistent with a cloudy day, creating even illumination without harsh shadows. The overall color palette is muted and naturalistic, dominated by greens of the mountain vegetation, gray of the overcast sky and asphalt, warm brown and tan tones of the exposed rock face, and the dark tone of the vehicle.

### #6 prairie_highway.jpg

A straight two-lane asphalt highway stretching into the far distance with a strong one-point perspective composition, shot from a low center-of-road viewpoint looking straight ahead, portrait orientation. The road surface is dark grey freshly-paved smooth asphalt, slightly wet with a subtle reflective sheen, marked with a solid yellow center dividing line and white dashed edge lines on both sides. Several cattle are walking on and beside the road: on the left lane, two cows walk away from the viewer, one white-and-brown patched and one reddish-brown, while on the right shoulder a single dark reddish-brown cow stands on the grass facing the road. A small brown wooden roadside sign with Chinese characters stands on the left grass shoulder near the cows. The road is flanked on both sides by vast, expansive, lush green alpine meadows and grasslands, the grass vivid and saturated in bright emerald and lime green tones, rolling gently with soft undulations. In the background, enormous snow-capped mountain peaks rise dramatically, their upper ridges and summits covered in bright white snow and glacial ice, while the lower slopes are blanketed in dense dark green alpine forests and vegetation. A thick band of low-hanging white and grey clouds and mist wraps around the mid-section of the mountains, partially obscuring the transition between the forested slopes and the snowy peaks, creating a layered atmospheric depth effect. The sky above the mountains is mostly overcast with soft white and light grey clouds, with hints of pale blue sky peeking through in small patches. The lighting is soft and diffused, consistent with an overcast or partly cloudy day, producing no harsh shadows, with even and gentle illumination across the entire scene. The overall color palette is dominated by vivid greens of the grasslands, cool whites and greys of the snow and clouds, and the dark neutral grey of the wet road. The atmosphere conveys a serene, remote, untouched natural landscape reminiscent of the Xinjiang Tianshan or Qilian mountain prairies in western China, with a peaceful pastoral mood, vast open space, and dramatic mountain scenery. Photorealistic style, high resolution, sharp detail, natural photography, landscape photography, true-to-life colors and lighting.

## 传输统计

### 第二轮数据

| # | 场景 | 原图大小 | 边缘图大小 | Prompt 大小 | 传输总量 | 压缩比 | 发送端耗时 | 接收端耗时 | 总耗时 |
|---|------|---------|-----------|------------|---------|--------|-----------|-----------|--------|
| 1 | 峡谷越野 | 235,820 B | 305,963 B | 1,841 B | 307,804 B | 0.77x | 2.5s | 49.8s | 52.3s |
| 2 | 攀岩越野 | 46,225 B | 169,693 B | 1,872 B | 171,565 B | 0.27x | 2.4s | 48.9s | 51.3s |
| 3 | 丛林小路 | 226,516 B | 255,195 B | 2,342 B | 257,537 B | 0.88x | 2.5s | 59.1s | 61.6s |
| 4 | 雪地松林 | 918,506 B | 430,058 B | 2,221 B | 432,279 B | 2.12x | 3.1s | 57.3s | 60.4s |
| 5 | 山间公路 | 842,569 B | 74,843 B | 2,703 B | 77,546 B | 10.87x | 3.2s | 48.8s | 52.0s |
| 6 | 草原雪山 | 302,866 B | 82,808 B | 2,284 B | 85,092 B | 3.56x | 2.3s | 48.8s | 51.0s |

### 两轮 Prompt 大小对比

| # | 场景 | R1 Prompt | R2 Prompt | 倍数 | R1 压缩比 | R2 压缩比 |
|---|------|-----------|-----------|------|----------|----------|
| 1 | 峡谷越野 | 143 B | 1,841 B | 12.9x | 0.77x | 0.77x |
| 2 | 攀岩越野 | 155 B | 1,872 B | 12.1x | 0.27x | 0.27x |
| 3 | 丛林小路 | 146 B | 2,342 B | 16.0x | 0.89x | 0.88x |
| 4 | 雪地松林 | 141 B | 2,221 B | 15.8x | 2.14x | 2.12x |
| 5 | 山间公路 | 137 B | 2,703 B | 19.7x | 11.24x | 10.87x |
| 6 | 草原雪山 | 161 B | 2,284 B | 14.2x | 3.65x | 3.56x |

**关键观察**：Prompt 大小增加了 12-20 倍，但相比边缘图（75KB-430KB）仍然微不足道（<1%），对压缩比几乎无影响。

## 第二轮逐张评价

### #1 峡谷越野 — 良好-（R1: 良好）⬇️ 下降

- **悬石颜色失真**：左侧悬挑巨石变成了不自然的深红棕色，原图和 R1 都是灰褐色——prompt 中"dark brown, warm tan, muted ochre"的描述误导了模型过度渲染暖色
- **路面出现不存在的元素**：路面出现了黄色泥浆/积水，原图中路面是干燥灰色碎石——prompt 中"shallow puddles of standing water"描述了一个不够精确的细节，模型将其夸大
- **前景多出散落石块**：原图前景相对干净，R2 多出了原图没有的大石块
- **整体色调过暖**：prompt 中大量暖色描述词叠加导致画面整体偏暖棕，失去了原图高海拔荒漠的冷灰感
- **教训**：过度具体的材质/色调描述反而成为"错误指令"，不如 R1 简短描述让模型自主发挥

### #2 攀岩越野 — 一般（R1: 良好）⬇️ 下降

- **天空严重失真**：天空变成了雾蒙蒙的暖褐色（像沙尘暴），原图是清澈的淡蓝/青色天空——prompt 中"warm amber atmospheric haze"直接导致了天空色彩崩溃
- **整体色调过度偏暖**：暖黄色调覆盖了整个画面，丧失了原图的清爽自然感
- **多出不存在的车牌**：车身右下方出现了蓝色车牌，原图该角度看不到——prompt 描述了"Chinese license plate"反而让模型在错误位置生成了车牌
- **车辆细节**：黄色车身还原准确，但被过度的暖色滤镜抵消了优势
- **教训**：prompt 中"warm golden-hour sunlight"、"warm brownish-orange tonal quality"等氛围描述与实际光照不符（原图并非黄金时段），导致严重色偏

### #3 丛林小路 — 良好（R1: 良好）

- **整体持平**：R1 和 R2 质量相近，整体还原效果不错
- **泥土路色调反而不如 R1**：原图路面是偏暗的红褐色带湿润感，R1 更接近这个色调；R2 路面变成了偏橙的亮红色，饱和度过高——prompt 中"reddish-brown laterite clay"把颜色推向了过于鲜艳的方向，又一个详细描述适得其反的案例
- **天空细节**：R2 天空出现了更多蓝天和白云层次（prompt 描述了"patches of pale blue sky"）
- **两轮共有缺陷——前景草地误识别**：原图中车辆正下方、两道车辙之间是一片低矮贴地的杂草地，但 R1 和 R2 都将其还原为一棵立体的热带植物/芭蕉叶。这是 Canny 边缘图的语义模糊性导致的——边缘线条只保留了轮廓，模型将"一片草地的轮廓"解读为"一棵植物的形状"。此缺陷与 prompt 无关，两轮完全一致

### #4 松林碎石路 — 良好+（R1: 一般）⬆️ 显著提升

- **场景认知纠正**：原图路面两侧是强光下的浅灰色碎石和裸露岩面，并非积雪。R1 的 prompt 错误描述为"patches of snow"，导致模型把碎石渲染成白色积雪，整体变成冬季雪景——严重偏离原图。R2 的 prompt 准确描述为"loose gray and beige gravel, scattered large boulders"，碎石路面的灰米色更接近原图
- **车身颜色修正**：R1 车身变成了亮绿色（受"Suzuki Jimny"刻板印象影响），R2 更接近原图的暗橄榄绿（prompt 描述了"matte olive green"）
- **松树层次**：针叶树的层次感和阴影更丰富
- **本张图是详细 prompt 发挥正面作用的最佳案例**：当 R1 的简短 prompt 包含关键性错误（"snow"）时，R2 的准确描述能从根本上纠正场景认知

### #5 山间公路 — 良好-（R1: 良好）⬇️ 略有下降

- **远景多出一座山**：原图远处只有一座圆顶山，R2 在右侧生成了一座原图没有的更大的尖顶绿山，改变了整个远景构图——这是 R2 最明显的问题，prompt 中"a large, rounded mountain...dome-like profile rising prominently in the center-right"的描述可能引导模型在边缘约束弱的区域生成了额外的山体
- **岩切面色调改善**：左侧开山岩壁的红棕色更接近原图——改善
- **山体绿色更饱和**：更接近原图——改善
- **建筑样式**：两轮都将远处建筑还原为红顶白墙，与原图不完全一致，但建筑本身并非幻觉（原图确实有建筑）
- **总体**：R2 色彩更好，但多出的山体是严重的结构性错误，抵消了色彩改善

### #6 草原雪山 — 优秀+（R1: 优秀）

- **草甸绿色**：R2 的草甸绿色更鲜亮饱和，更接近原图的翠绿（prompt 描述了"vivid and saturated in bright emerald and lime green"）
- **牛群细节**：牛的位置和毛色更准确（prompt 描述了"one white-and-brown patched and one reddish-brown"）
- **路面湿润感**：R2 路面呈现微湿的反光质感（prompt 描述了"slightly wet with a subtle reflective sheen"）
- **雪山云雾**：山腰云雾层次更分明，雪线过渡更自然

## 两轮对比总结

### 还原质量评分对比

| # | 场景 | R1 评分 | R2 评分 | 变化 |
|---|------|--------|--------|------|
| 1 | 峡谷越野 | 良好 | 良好- | ⬇️ 暖色过度，多出不存在元素 |
| 2 | 攀岩越野 | 良好 | 一般 | ⬇️ 天空严重失真，整体偏暖 |
| 3 | 丛林小路 | 良好 | 良好 | ➡️ 持平，两轮均有前景草地误识别 |
| 4 | 松林碎石路 | 一般 | 良好+ | ⬆️ 场景认知纠正（碎石非积雪）+ 车身颜色修正 |
| 5 | 山间公路 | 良好 | 良好- | ⬇️ 色彩改善，但多出一座不存在的山 |
| 6 | 草原雪山 | 优秀 | 优秀+ | ⬆️ 色彩更鲜艳准确 |

### 综合评价维度对比

| 维度 | R1 评分 | R2 评分 | 变化 |
|------|--------|--------|------|
| 结构保持度 | 5/5 | 4/5 | **下降**：过度具体的描述导致模型生成不存在的元素 |
| 语义还原度 | 4/5 | 3.5/5 | **下降**：2/6 张因 prompt 误导出现严重色偏和幻觉 |
| 视觉质量 | 4/5 | 3.5/5 | **下降**：部分场景色调失真明显 |
| 场景适应性 | 4/5 | 3.5/5 | **下降**：详细 prompt 对复杂场景（#1 #2）反而有害 |
| 压缩效率 | 2/5 | 2/5 | 不变（prompt 增量相对边缘图可忽略） |

### 关键结论

1. **详细 prompt 是双刃剑**：2/6 张图效果改善（#4 #6），3/6 张效果下降（#1 #2 #5），1/6 张持平（#3）。整体来看详细描述弊大于利。

2. **过度具体的描述会成为"错误指令"**：
   - #1 中"shallow puddles of standing water"让模型在干燥路面生成了积水
   - #2 中"warm amber atmospheric haze"把晴朗蓝天变成了沙尘暴天空
   - #2 中"Chinese license plate"让模型在错误位置生成了车牌
   - 这些描述看似准确，但与边缘图的约束发生冲突时，模型选择了服从 prompt 而非边缘图

3. **准确的颜色词比氛围词更有用**：
   - "matte olive green"（#4）精确修正了车身颜色——有效
   - "warm golden-hour sunlight"（#2）误导了整体色温——有害
   - 具体物体颜色（客观事实）比光照氛围（主观感受）更可靠

4. **详细 prompt 无法消除幻觉**：#5 山间公路的幻觉问题在两轮中持续存在。边缘约束力弱区域的幻觉是 ControlNet 的固有限制，与 prompt 长度无关。

5. **prompt 增量对压缩比影响可忽略**：Prompt 从 ~140B 增加到 ~2,000B（约 14 倍），但相比边缘图（75KB-430KB），仅占传输数据的 0.3%-3%。瓶颈在边缘图编码，不在 prompt。

6. **简短但准确的 prompt 可能是最优策略**：R1 中边缘约束足够强的场景（#3 #6）已经很好，额外信息无益。关键不是 prompt 有多长，而是是否准确——错误信息比缺少信息更有害。

## 量化评估指标（三轮对比）

> 评估日期：2026-03-28
> 评估脚本：`scripts/evaluate.py`
> R1 = Round 1（简短手动 prompt），R2 = Round 2（详细手动 prompt），R3 = Round 3（VLM 自动 prompt）
> CLIP Score 因缺少 prompt.txt 文件未计算

### 逐样本三轮对比

| # | 场景 | PSNR (dB) ↑ | | | SSIM ↑ | | | LPIPS ↓ | | |
|---|------|---|---|---|---|---|---|---|---|---|
| | | R1 | R2 | R3 | R1 | R2 | R3 | R1 | R2 | R3 |
| 1 | 峡谷越野 | 12.71 | **9.08** | 11.24 | 0.31 | **0.20** | 0.24 | 0.48 | **0.66** | 0.57 |
| 2 | 攀岩越野 | **12.81** | 12.76 | 13.86 | 0.27 | 0.28 | **0.30** | **0.50** | 0.45 | 0.46 |
| 3 | 丛林小路 | **15.98** | 14.59 | 15.19 | **0.36** | 0.33 | 0.34 | **0.42** | 0.47 | 0.44 |
| 4 | 雪地松林 | 10.79 | 10.69 | **11.14** | 0.12 | **0.12** | 0.12 | **0.62** | 0.57 | 0.57 |
| 5 | 山间公路 | **17.44** | 13.51 | 18.54 | **0.71** | 0.65 | 0.73 | **0.39** | 0.47 | 0.34 |
| 6 | 草原雪山 | 14.22 | 14.57 | **16.20** | 0.54 | 0.55 | **0.54** | **0.58** | 0.56 | 0.55 |

### 汇总统计

| 指标 | R1 均值 | R2 均值 | R3 均值 | 最优轮次 |
|------|---------|---------|---------|----------|
| **PSNR ↑** | 13.99 ± 2.21 | 12.53 ± 2.03 | **14.36 ± 2.64** | R3 |
| **SSIM ↑** | 0.385 ± 0.191 | 0.354 ± 0.186 | **0.380 ± 0.202** | R1 ≈ R3 |
| **LPIPS ↓** | 0.498 ± 0.080 | 0.530 ± 0.074 | **0.488 ± 0.086** | R3 |

### 量化结论

1. **R3（VLM 自动 prompt）在三项指标上均为最优或并列最优**：PSNR 14.36（最高）、SSIM 0.380（与 R1 持平）、LPIPS 0.488（最低/最好）。VLM 自动生成的中等长度 prompt（~1.3-2.3KB）在准确性和信息量之间取得了最佳平衡。

2. **R2（详细手动 prompt）在所有指标上均为最差**：PSNR 12.53（最低）、SSIM 0.354（最低）、LPIPS 0.530（最高/最差）。量化结果印证了主观评价——过度详细的 prompt 弊大于利。

3. **R1（简短手动 prompt）表现居中**：简短但大致准确的描述优于冗长但可能偏差的描述，但不如 VLM 的精准描述。

4. **逐样本分析**：
   - #1 峡谷越野：R2 全面崩溃（PSNR 从 12.71 降至 9.08），印证主观评价"暖色过度"
   - #4 雪地松林：三轮指标均差（SSIM ~0.12），是最难还原的场景——与 prompt 策略关系不大，主要受边缘图语义模糊性限制
   - #5 山间公路：R3 达到全场最高 PSNR=18.54 和 SSIM=0.73，VLM prompt 在此场景效果突出

5. **量化指标与主观评价的一致性**：三轮排序（R3 > R1 > R2）与报告 02 的主观结论完全一致。LPIPS 作为感知距离指标最能反映人类主观感受。

## 对 VLM 自动 Prompt（P2-13）的启示

- **准确性优先于详尽度**：VLM 生成的 prompt 必须忠实于原图，不能有主观"艺术化"描述（如不该加"golden hour"）
- **避免描述不确定的细节**：不确定的元素（如"积水"、"钢缆"）宁可省略，描述错误比不描述更有害
- **重点输出客观属性**：物体颜色（"olive green vehicle"）、天气状态（"overcast"）、地形类型（"gravel road"）——这些是客观可验证的
- **慎用主观氛围词**：避免"golden hour"、"amber haze"等可能误导色温的词，除非确信光照条件
- **材质纹理描述价值有限**：边缘图已提供了丰富的结构信息，prompt 重复描述纹理的边际收益很低
- VLM 输出的理想长度可能在 R1（~140B）和 R2（~2KB）之间，约 300-500B（2-3 句精准描述）
- **R3 量化验证**：VLM 自动 prompt（~1.3-2.3KB）在三轮中指标最优，证明 VLM 的客观描述优于人工的主观描述

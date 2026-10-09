using TMPro;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

namespace AcrophobiaVR
{
    /// <summary>
    /// Builds world-space uGUI at runtime so no prefabs are needed. Canvases work with both
    /// XR controller rays (TrackedDeviceGraphicRaycaster) and the mouse in desktop mode.
    /// </summary>
    public static class UIFactory
    {
        public static readonly Color PanelColor = new Color(0.07f, 0.11f, 0.17f, 0.92f);
        public static readonly Color Accent = new Color(0.36f, 0.78f, 0.98f);
        public static readonly Color Calm = new Color(0.45f, 0.85f, 0.6f);
        public static readonly Color Warn = new Color(1f, 0.62f, 0.3f);
        public static readonly Color ButtonColor = new Color(0.18f, 0.27f, 0.4f, 1f);
        public static readonly Color Gold = new Color(1f, 0.84f, 0.3f);

        /// <summary>Set by DesktopRig. Mouse raycasting on world canvases is only enabled without a headset,
        /// otherwise the plain GraphicRaycaster would also react to controller rays at bogus screen positions.</summary>
        public static bool DesktopMode;

        static Font font;
        static Sprite circle;
        static Sprite rounded;

        public static Font Font
        {
            get
            {
                if (font == null) font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
                return font;
            }
        }

        /// <summary>Procedurally generated soft circle sprite (breathing orb, stars, gauges).</summary>
        public static Sprite Circle
        {
            get
            {
                if (circle != null) return circle;
                const int size = 128;
                var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
                float r = size * 0.5f;
                for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), new Vector2(r, r));
                    tex.SetPixel(x, y, new Color(1, 1, 1, Mathf.Clamp01(r - d)));
                }
                tex.Apply();
                circle = Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
                return circle;
            }
        }

        /// <summary>Rounded-rectangle 9-slice sprite for panels and buttons.</summary>
        public static Sprite Rounded
        {
            get
            {
                if (rounded != null) return rounded;
                const int size = 64;
                const float radius = 18f;
                var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
                for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float cx = Mathf.Clamp(x + 0.5f, radius, size - radius);
                    float cy = Mathf.Clamp(y + 0.5f, radius, size - radius);
                    float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), new Vector2(cx, cy));
                    tex.SetPixel(x, y, new Color(1, 1, 1, Mathf.Clamp01(radius - d)));
                }
                tex.Apply();
                rounded = Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f, 0,
                    SpriteMeshType.FullRect, new Vector4(radius, radius, radius, radius));
                return rounded;
            }
        }

        public static void EnsureEventSystem()
        {
            if (Object.FindFirstObjectByType<EventSystem>() != null) return;
            var go = new GameObject("EventSystem");
            go.AddComponent<EventSystem>();
            go.AddComponent<XRUIInputModule>();
        }

        /// <summary>Creates a world-space canvas. Size is in canvas pixels; 1 pixel = 1 mm by default.</summary>
        public static Canvas CreateWorldCanvas(string name, Vector2 sizePx, float metersPerPixel = 0.001f, Transform parent = null)
        {
            EnsureEventSystem();
            var go = new GameObject(name, typeof(RectTransform));
            if (parent != null) go.transform.SetParent(parent, false);
            var canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;
            canvas.worldCamera = Camera.main;
            canvas.sortingOrder = 10;
            go.AddComponent<CanvasScaler>().dynamicPixelsPerUnit = 4f;
            go.AddComponent<GraphicRaycaster>().enabled = DesktopMode;
            go.AddComponent<TrackedDeviceGraphicRaycaster>();
            var rt = (RectTransform)go.transform;
            rt.sizeDelta = sizePx;
            go.transform.localScale = Vector3.one * metersPerPixel;
            return canvas;
        }

        public static Image Panel(Transform parent, Color color, Vector2 pos, Vector2 size, bool roundedCorners = true)
        {
            var img = new GameObject("Panel", typeof(RectTransform)).AddComponent<Image>();
            img.transform.SetParent(parent, false);
            img.color = color;
            if (roundedCorners)
            {
                img.sprite = Rounded;
                img.type = Image.Type.Sliced;
            }
            img.rectTransform.anchoredPosition = pos;
            img.rectTransform.sizeDelta = size;
            return img;
        }

        public static Image FullPanel(Transform parent, Color color)
        {
            var img = Panel(parent, color, Vector2.zero, Vector2.zero);
            img.rectTransform.anchorMin = Vector2.zero;
            img.rectTransform.anchorMax = Vector2.one;
            img.rectTransform.offsetMin = Vector2.zero;
            img.rectTransform.offsetMax = Vector2.zero;
            return img;
        }

        /// <summary>
        /// Crisp TextMeshPro (signed-distance-field) label. SDF text stays sharp at any distance and in a headset,
        /// unlike the legacy bitmap Text which looks blurry/jagged in world space.
        /// </summary>
        public static TextMeshProUGUI Label(Transform parent, string text, int fontSize, Vector2 pos, Vector2 size,
            TextAnchor align = TextAnchor.MiddleCenter, Color? color = null, FontStyle style = FontStyle.Normal)
        {
            var t = new GameObject("Label", typeof(RectTransform)).AddComponent<TextMeshProUGUI>();
            t.transform.SetParent(parent, false);
            if (TMP_Settings.defaultFontAsset != null) t.font = TMP_Settings.defaultFontAsset;
            t.text = text;
            t.fontSize = fontSize;
            t.fontStyle = style == FontStyle.Bold || style == FontStyle.BoldAndItalic ? FontStyles.Bold
                : style == FontStyle.Italic ? FontStyles.Italic : FontStyles.Normal;
            t.alignment = ToTmp(align);
            t.color = color ?? Color.white;
            t.textWrappingMode = TextWrappingModes.Normal;
            t.overflowMode = TextOverflowModes.Overflow;
            t.richText = true;
            t.raycastTarget = false;
            t.rectTransform.anchoredPosition = pos;
            t.rectTransform.sizeDelta = size;
            return t;
        }

        static TextAlignmentOptions ToTmp(TextAnchor a)
        {
            switch (a)
            {
                case TextAnchor.UpperLeft: return TextAlignmentOptions.TopLeft;
                case TextAnchor.UpperCenter: return TextAlignmentOptions.Top;
                case TextAnchor.UpperRight: return TextAlignmentOptions.TopRight;
                case TextAnchor.MiddleLeft: return TextAlignmentOptions.Left;
                case TextAnchor.MiddleRight: return TextAlignmentOptions.Right;
                case TextAnchor.LowerLeft: return TextAlignmentOptions.BottomLeft;
                case TextAnchor.LowerCenter: return TextAlignmentOptions.Bottom;
                case TextAnchor.LowerRight: return TextAlignmentOptions.BottomRight;
                default: return TextAlignmentOptions.Center;
            }
        }

        public static Button Button(Transform parent, string text, Vector2 pos, Vector2 size, Color color,
            UnityAction onClick, int fontSize = 34)
        {
            var img = Panel(parent, color, pos, size);
            img.name = "Button " + text;
            var b = img.gameObject.AddComponent<Button>();
            var colors = b.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1.25f, 1.25f, 1.25f, 1f);
            colors.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
            colors.disabledColor = new Color(0.5f, 0.5f, 0.5f, 0.6f);
            colors.colorMultiplier = 1.4f;
            b.colors = colors;
            b.onClick.AddListener(ProceduralAudio.PlayClick);
            if (onClick != null) b.onClick.AddListener(onClick);
            var label = Label(img.transform, text, fontSize, Vector2.zero, size);
            label.rectTransform.anchorMin = Vector2.zero;
            label.rectTransform.anchorMax = Vector2.one;
            label.rectTransform.sizeDelta = new Vector2(-16, -8);
            return b;
        }

        public static Image CircleImage(Transform parent, Color color, Vector2 pos, float diameter)
        {
            var img = new GameObject("Circle", typeof(RectTransform)).AddComponent<Image>();
            img.transform.SetParent(parent, false);
            img.sprite = Circle;
            img.color = color;
            img.raycastTarget = false;
            img.rectTransform.anchoredPosition = pos;
            img.rectTransform.sizeDelta = new Vector2(diameter, diameter);
            return img;
        }

        /// <summary>Radial-fill ring used for gaze/hold progress.</summary>
        public static Image Ring(Transform parent, Color color, Vector2 pos, float diameter)
        {
            var img = CircleImage(parent, color, pos, diameter);
            img.type = Image.Type.Filled;
            img.fillMethod = Image.FillMethod.Radial360;
            img.fillOrigin = (int)Image.Origin360.Top;
            img.fillClockwise = true;
            img.fillAmount = 0f;
            return img;
        }

        /// <summary>Plain-text star count (no special glyphs, works with any font).</summary>
        public static string Stars(int count, int max = 3) => count + " / " + max + " stars";

        static Sprite star;

        /// <summary>Procedurally drawn, anti-aliased five-point star sprite.</summary>
        public static Sprite Star
        {
            get
            {
                if (star != null) return star;
                const int size = 128;
                var pts = new Vector2[10];
                for (int i = 0; i < 10; i++)
                {
                    float a = Mathf.PI / 2f + i * Mathf.PI / 5f;
                    float r = (i % 2 == 0 ? 0.48f : 0.2f) * size;
                    pts[i] = new Vector2(size * 0.5f + Mathf.Cos(a) * r, size * 0.52f + Mathf.Sin(a) * r);
                }
                var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
                for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    int inside = 0;
                    for (int sy = 0; sy < 4; sy++)
                    for (int sx = 0; sx < 4; sx++)
                        if (InPolygon(new Vector2(x + (sx + 0.5f) / 4f, y + (sy + 0.5f) / 4f), pts)) inside++;
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, inside / 16f));
                }
                tex.Apply();
                star = Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
                return star;
            }
        }

        static bool InPolygon(Vector2 p, Vector2[] poly)
        {
            bool inside = false;
            for (int i = 0, j = poly.Length - 1; i < poly.Length; j = i++)
                if ((poly[i].y > p.y) != (poly[j].y > p.y) &&
                    p.x < (poly[j].x - poly[i].x) * (p.y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x)
                    inside = !inside;
            return inside;
        }

        static Sprite heart;

        /// <summary>Procedurally drawn, anti-aliased heart sprite (lives).</summary>
        public static Sprite Heart
        {
            get
            {
                if (heart != null) return heart;
                const int size = 128;
                var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
                for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    int inside = 0;
                    for (int sy = 0; sy < 4; sy++)
                    for (int sx = 0; sx < 4; sx++)
                    {
                        // Classic implicit heart curve: (x^2 + y^2 - 1)^3 - x^2 y^3 <= 0
                        float u = ((x + (sx + 0.5f) / 4f) / size - 0.5f) * 2.6f;
                        float v = ((y + (sy + 0.5f) / 4f) / size - 0.45f) * 2.6f;
                        float a = u * u + v * v - 1f;
                        if (a * a * a - u * u * v * v * v <= 0f) inside++;
                    }
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, inside / 16f));
                }
                tex.Apply();
                heart = Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
                return heart;
            }
        }

        public static readonly Color HeartRed = new Color(1f, 0.3f, 0.36f);

        /// <summary>A row of red (remaining) and dim (lost) hearts. Returns the images so callers can refresh them.</summary>
        public static Image[] HeartRow(Transform parent, int count, int max, Vector2 center, float size)
        {
            var row = new Image[max];
            for (int i = 0; i < max; i++)
            {
                var img = new GameObject("Heart", typeof(RectTransform)).AddComponent<Image>();
                img.transform.SetParent(parent, false);
                img.sprite = Heart;
                img.raycastTarget = false;
                img.rectTransform.anchoredPosition = center + new Vector2((i - (max - 1) * 0.5f) * size * 1.15f, 0f);
                img.rectTransform.sizeDelta = new Vector2(size, size);
                row[i] = img;
            }
            SetHearts(row, count);
            return row;
        }

        public static void SetHearts(Image[] row, int count)
        {
            if (row == null) return;
            for (int i = 0; i < row.Length; i++)
                if (row[i] != null) row[i].color = i < count ? HeartRed : new Color(1f, 1f, 1f, 0.2f);
        }

        /// <summary>A row of gold (earned) and dim (missing) star icons.</summary>
        public static void StarRow(Transform parent, int count, int max, Vector2 center, float size)
        {
            for (int i = 0; i < max; i++)
            {
                var img = new GameObject("Star", typeof(RectTransform)).AddComponent<Image>();
                img.transform.SetParent(parent, false);
                img.sprite = Star;
                img.raycastTarget = false;
                img.color = i < count ? Gold : new Color(1f, 1f, 1f, 0.22f);
                img.rectTransform.anchoredPosition = center + new Vector2((i - (max - 1) * 0.5f) * size * 1.15f, 0f);
                img.rectTransform.sizeDelta = new Vector2(size, size);
            }
        }
    }
}
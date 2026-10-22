/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com> */
/**
 * Chatboo charts v2 — hydrate Chart.js or ECharts under server-rendered tables.
 * Engine: data-ai-chart-engine="echarts"|"chartjs" (default chartjs),
 * or window.CHATBOO_CHART_ENGINE for global override (spike / QA).
 * Source of truth: data-ai-dataset JSON (not formatted DOM cells).
 */
(function (global) {
    "use strict";

    var MAX_SERIES = 12;
    var PIE_MAX_CATS = 8;
    var RADAR_MIN_CATS = 3;
    var RADAR_MAX_CATS = 12;
    var SHOW_MODE_TABLE_CHART = "show-table";
    var SHOW_MODE_CHART_TABLE = "show-chart";
    var SHOW_MODE_TABLE_ONLY = "table";
    var ENGINE_CHARTJS = "chartjs";
    var ENGINE_ECHARTS = "echarts";
    // Ratio para decidir barra vs línea en modo combinado (no eje).
    var SCALE_RATIO_DUAL = 3;
    // Solo magnitudes absolutas extremas (p.ej. € vs nº) → 2º eje.
    // Umbral bajo (3) hacía dual Facturación/Salarios (~4–5×) y mentía la comparación.
    var SCALE_RATIO_DUAL_EXTREME = 50;
    var SKIP_KEYS = { id: 1, __model: 1 };
    // Columnas ratio/% → eje derecho cuando conviven con importes absolutos.
    var RATIO_KEY_RE =
        /%|percent|pct\b|ratio|tasa|margen|índice|indice|\bshare\b|\bpeso\b/i;
    // Auto-chart Y: solo forma de clave (dinero / % / contador), sin dominio de negocio.
    var MONEY_KEY_RE =
        /amount|total|importe|monto|saldo|balance|revenue|ingreso|precio|price|coste|cost\b|debe|haber|beneficio|deuda|pend|subtotal|neto|gasto|expense|sales?|venta|factur|payroll|n[oó]mina|salary|sueldo|wage|pago|payment|cobro|recib|honor/i;
    var COUNT_KEY_RE =
        /\bcount\b|qty|cantidad|n[uú]mero|\bnum\b|n[º°]|uds?\b|units?|horas?|hours?|d[ií]as?|days?|\bitems?\b|\bn\b/i;

    var ChartLib = null;
    var EchartsLib = null;
    var showSeriesStats = false;

    function bindEngines(chart, echarts) {
        if (typeof chart === "function") {
            ChartLib = chart;
        }
        if (echarts) {
            EchartsLib = echarts;
        }
    }

    function setShowSeriesStats(value) {
        showSeriesStats = !!value;
    }

    function getShowSeriesStats() {
        return !!showSeriesStats;
    }

    // English msgids; the chat client passes them through its own _t().
    var LABELS = {
        chart: "Chart",
        data: "Data",
        canvas: "Canvas",
        canvasTitle: "Lay out the tables of this answer as a page",
        canvasBuilding: "Building the page…",
        canvasOpen: "Open page",
        canvasFailed: "No page was built.",
        canvasCancel: "Building the page. Click to cancel.",
    };

    function setLabels(labels) {
        if (!labels || typeof labels !== "object") {
            return;
        }
        Object.keys(LABELS).forEach(function (key) {
            if (typeof labels[key] === "string" && labels[key]) {
                LABELS[key] = labels[key];
            }
        });
    }

    function label(key) {
        return LABELS[key] || key;
    }

    var TIME_KEY_RE = /^(year|año|ano|periodo|period|fecha|date|mes|month|trimestre|quarter|semana|week|h[12]|q[1-4]|m\d{1,2})$/i;
    var TIME_VAL_RE = /^(?:(?:19|20)\d{2}|h[12]|q[1-4]|m(?:0?[1-9]|1[0-2])|(?:19|20)\d{2}[-/]\d{1,2}(?:[-/]\d{1,2})?)$/i;
    var PERIOD_SERIES_RE =
        /^(?:t[1-4]|q[1-4]|h[1-2])(?:\s*(?:19|20)\d{2})?$|^(?:trimestre|quarter|cuarto)\s*[1-4]|^mes\s*(?:0?[1-9]|1[0-2])$/i;

    function isPeriodSeriesKey(key) {
        var s = String(key || "").trim();
        if (!s) {
            return false;
        }
        if (PERIOD_SERIES_RE.test(s)) {
            return true;
        }
        if (isTimeLikeKey(s)) {
            return true;
        }
        return /^(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|jan|apr|aug|dec)/i.test(s);
    }

    function seriesKeysArePeriodBuckets(keys) {
        if (!keys || keys.length < 2) {
            return false;
        }
        var hits = 0;
        var i;
        for (i = 0; i < keys.length; i++) {
            if (isPeriodSeriesKey(keys[i])) {
                hits++;
            }
        }
        return hits >= 2 && hits >= keys.length * 0.6;
    }

    function parsePeriodSortKey(key) {
        var s = String(key || "").trim().toLowerCase();
        var year = 0;
        var period = 0;
        var ym = s.match(/(19|20)\d{2}/);
        if (ym) {
            year = parseInt(ym[0], 10);
        }
        var tm = s.match(/t(?:rimestre|)\s*([1-4])|^t([1-4])\b|cuarto\s*([1-4])/);
        if (tm) {
            period = parseInt(tm[1] || tm[2] || tm[3], 10);
        }
        var qm = s.match(/q(?:uart(?:er|al)?|)\s*([1-4])|^q([1-4])\b/);
        if (qm) {
            period = parseInt(qm[1] || qm[2], 10);
        }
        var hm = s.match(/\bh([12])\b/);
        if (hm) {
            period = parseInt(hm[1], 10);
        }
        var mm = s.match(/mes\s*(0?[1-9]|1[0-2])/);
        if (mm) {
            period = parseInt(mm[1], 10);
        }
        var months = {
            ene: 1, jan: 1, feb: 2, mar: 3, abr: 4, apr: 4, may: 5, jun: 6,
            jul: 7, ago: 8, aug: 8, sep: 9, oct: 10, nov: 11, dic: 12, dec: 12,
        };
        var mon = s.match(/^([a-z]{3})\b/);
        if (mon && months[mon[1]]) {
            period = months[mon[1]];
        }
        return { year: year, period: period, raw: s };
    }

    function orderPeriodSeriesKeys(keys) {
        return keys.slice().sort(function (a, b) {
            var pa = parsePeriodSortKey(a);
            var pb = parsePeriodSortKey(b);
            if (pa.year !== pb.year) {
                return pa.year - pb.year;
            }
            if (pa.period !== pb.period) {
                return pa.period - pb.period;
            }
            return pa.raw.localeCompare(pb.raw);
        });
    }

    function parseNumber(val) {
        if (val === null || val === undefined || val === "") {
            return null;
        }
        if (typeof val === "number" && isFinite(val)) {
            return val;
        }
        if (typeof val === "boolean") {
            return null;
        }
        var s = String(val).trim();
        if (!s) {
            return null;
        }
        var compact = s.replace(/\s/g, "").replace(/[€$£¥]/g, "");
        if (/[a-zA-ZÀ-ÿ]/.test(compact)) {
            if (!/^-?\d+(\.\d+)?[eE][+-]?\d+$/.test(compact)) {
                return null;
            }
        }
        if (/^-?\d{1,3}(\.\d{3})+(,\d+)?$/.test(compact)) {
            compact = compact.replace(/\./g, "").replace(",", ".");
        } else if (/^-?\d{1,3}(,\d{3})+(\.\d+)?$/.test(compact)) {
            compact = compact.replace(/,/g, "");
        } else if (compact.indexOf(",") >= 0 && compact.indexOf(".") < 0) {
            compact = compact.replace(",", ".");
        } else {
            compact = compact.replace(/[^\d.\-eE]/g, "");
        }
        if (!compact || !/\d/.test(compact)) {
            return null;
        }
        var n = Number(compact);
        return isFinite(n) ? n : null;
    }

    function humanizeKey(key) {
        return String(key || "")
            .replace(/_/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    function columnKeys(rows) {
        if (!rows || !rows.length) {
            return [];
        }
        var keys = [];
        var seen = {};
        rows.forEach(function (row) {
            Object.keys(row || {}).forEach(function (k) {
                if (seen[k] || k.charAt(0) === "_" || SKIP_KEYS[k]) {
                    return;
                }
                seen[k] = 1;
                keys.push(k);
            });
        });
        return keys;
    }

    function isNumericColumn(rows, key) {
        var seen = 0;
        var ok = 0;
        for (var i = 0; i < rows.length && i < 40; i++) {
            var v = rows[i][key];
            if (v === null || v === undefined || v === "") {
                continue;
            }
            seen++;
            if (parseNumber(v) !== null) {
                ok++;
            }
        }
        return seen > 0 && ok >= Math.max(1, Math.floor(seen * 0.8));
    }

    function isTimeLikeKey(key) {
        return TIME_KEY_RE.test(String(key).replace(/\s+/g, ""));
    }

    function isTimeLikeValues(rows, key) {
        var hits = 0;
        var seen = 0;
        for (var i = 0; i < rows.length && i < 40; i++) {
            var v = rows[i][key];
            if (v === null || v === undefined || v === "") {
                continue;
            }
            seen++;
            var s = String(v).trim();
            if (TIME_VAL_RE.test(s) || /(?:19|20)\d{2}/.test(s)) {
                hits++;
            }
        }
        return seen > 0 && hits >= Math.max(1, Math.floor(seen * 0.6));
    }

    function pickCategory(rows, keys, numericKeys) {
        for (var i = 0; i < keys.length; i++) {
            if (isTimeLikeKey(keys[i]) || isTimeLikeValues(rows, keys[i])) {
                return keys[i];
            }
        }
        var nonNum = keys.filter(function (k) {
            return numericKeys.indexOf(k) < 0;
        });
        return nonNum.length ? nonNum[0] : null;
    }

    function seriesValues(rows, key) {
        return rows.map(function (r) {
            var n = parseNumber(r[key]);
            return n === null ? 0 : n;
        });
    }

    function valueRange(values) {
        if (!values || !values.length) {
            return 0;
        }
        var min = Infinity;
        var max = -Infinity;
        for (var i = 0; i < values.length; i++) {
            var v = values[i];
            if (typeof v !== "number" || !isFinite(v)) {
                continue;
            }
            if (v < min) {
                min = v;
            }
            if (v > max) {
                max = v;
            }
        }
        if (!isFinite(min) || !isFinite(max)) {
            return 0;
        }
        return max - min;
    }

    function monotonicScore(values) {
        if (!values || values.length < 2) {
            return 0;
        }
        if (valueRange(values) <= 0) {
            return 0;
        }
        var desc = 0;
        var asc = 0;
        for (var i = 1; i < values.length; i++) {
            if (values[i] <= values[i - 1]) {
                desc++;
            }
            if (values[i] >= values[i - 1]) {
                asc++;
            }
        }
        return Math.max(desc, asc) / (values.length - 1);
    }

    function absMax(values) {
        var m = 0;
        for (var i = 0; i < values.length; i++) {
            var a = Math.abs(values[i]);
            if (a > m) {
                m = a;
            }
        }
        return m;
    }

    /**
     * Métrica dominante = eje / título (no reordena series).
     * Pondera monotonía × log(rango) para no elegir columnas casi planas.
     */
    function pickDominantMetric(rows, seriesKeys) {
        if (!seriesKeys.length) {
            return null;
        }
        if (seriesKeys.length === 1) {
            return seriesKeys[0];
        }
        var bestKey = seriesKeys[0];
        var bestScore = -1;
        for (var i = 0; i < seriesKeys.length; i++) {
            var key = seriesKeys[i];
            var vals = seriesValues(rows, key);
            var mono = monotonicScore(vals);
            var range = valueRange(vals);
            if (mono <= 0 || range <= 0) {
                continue;
            }
            var score = mono * Math.log10(range + 1);
            score += (seriesKeys.length - i) * 0.001;
            if (score > bestScore) {
                bestScore = score;
                bestKey = key;
            }
        }
        return bestKey;
    }

    function orderSeriesKeys(rows, seriesKeys) {
        if (seriesKeysArePeriodBuckets(seriesKeys)) {
            return orderPeriodSeriesKeys(seriesKeys);
        }
        return seriesKeys.slice();
    }

    function isRatioLikeKey(key) {
        return RATIO_KEY_RE.test(String(key || ""));
    }

    function isMoneyLikeKey(key) {
        return MONEY_KEY_RE.test(String(key || ""));
    }

    function isCountLikeKey(key) {
        return COUNT_KEY_RE.test(String(key || ""));
    }

    /** Serie Y apta para auto-gráfico: dinero, %/ratio o contador (forma de clave). */
    function isChartMetricKey(key) {
        return isMoneyLikeKey(key) || isRatioLikeKey(key) || isCountLikeKey(key);
    }

    /**
     * Dual Y solo si mezclamos absolutos + ratio/%, o hueco de escala extremo
     * (€ vs conteos). Nunca por un ratio moderado entre dos series en la misma
     * unidad (Facturación vs Salarios): eso infla la serie menor y engaña.
     */
    function needsDualAxis(series) {
        if (!series || series.length < 2) {
            return false;
        }
        var maxes = [];
        var ratioCount = 0;
        var absCount = 0;
        var i;
        for (i = 0; i < series.length; i++) {
            var m = absMax(series[i].values);
            if (m > 0) {
                maxes.push(m);
            }
            if (isRatioLikeKey(series[i].key)) {
                ratioCount++;
            } else if (m > 0) {
                absCount++;
            }
        }
        if (ratioCount > 0 && absCount > 0) {
            return true;
        }
        if (maxes.length < 2) {
            return false;
        }
        var hi = Math.max.apply(null, maxes);
        var lo = Math.min.apply(null, maxes);
        return lo > 0 && hi / lo >= SCALE_RATIO_DUAL_EXTREME;
    }

    /** Override desde data-ai-dual-axis o toggle UI; null = auto. */
    function parseDualAxisAttr(raw) {
        if (raw === null || raw === undefined) {
            return null;
        }
        var v = String(raw).trim().toLowerCase();
        if (!v || v === "auto") {
            return null;
        }
        if (v === "0" || v === "false" || v === "off" || v === "single" || v === "one") {
            return false;
        }
        if (v === "1" || v === "true" || v === "on" || v === "dual" || v === "two") {
            return true;
        }
        return null;
    }

    var KPI_CAT_RE = /^(metric|indicador|indicator|kpi|concepto|concept|label)$/i;

    function isKpiLabelValueMeta(meta) {
        if (!meta || !meta.categoryKey || !meta.seriesKeys || meta.seriesKeys.length !== 1) {
            return false;
        }
        return KPI_CAT_RE.test(String(meta.categoryKey).trim());
    }

    function categoryAxisLabel(labels) {
        var maxLen = 0;
        var i;
        for (i = 0; i < (labels || []).length; i++) {
            maxLen = Math.max(maxLen, String(labels[i] || "").length);
        }
        var rotate = 0;
        if (maxLen > 18 || (labels && labels.length > 6)) {
            rotate = 40;
        }
        if (maxLen > 28) {
            rotate = 50;
        }
        var style = {
            rotate: rotate,
            interval: 0,
            hideOverlap: true,
        };
        if (maxLen > 14) {
            style.width = 88;
            style.overflow = "truncate";
            style.ellipsis = "…";
        }
        return style;
    }

    function applyDualAxisOverride(meta, block) {
        if (!meta || !block) {
            return meta;
        }
        var forced = parseDualAxisAttr(block.getAttribute("data-ai-dual-axis"));
        if (forced === null && block._chatbooDualAxisForce !== undefined) {
            forced = block._chatbooDualAxisForce;
        }
        if (forced === null) {
            return meta;
        }
        meta.dualAxis = !!forced && meta.series.length >= 2 && !meta.periodBuckets;
        return meta;
    }

    function allSeriesNonNegative(series) {
        var i;
        var j;
        for (i = 0; i < series.length; i++) {
            for (j = 0; j < series[i].values.length; j++) {
                if (series[i].values[j] < 0) {
                    return false;
                }
            }
        }
        return true;
    }

    function analyzeDataset(rows, opts) {
        opts = opts || {};
        var keys = columnKeys(rows);
        var numericKeys = keys.filter(function (k) {
            return isNumericColumn(rows, k);
        });
        var categoryKey = pickCategory(rows, keys, numericKeys);
        if (!categoryKey) {
            return null;
        }
        var seriesCandidates = numericKeys.filter(function (k) {
            return k !== categoryKey;
        });
        // Auto (metricsOnly): solo dinero / % / contador. Petición explícita: todas.
        if (opts.metricsOnly) {
            seriesCandidates = seriesCandidates.filter(isChartMetricKey);
        }
        var seriesKeys = orderSeriesKeys(rows, seriesCandidates).slice(0, MAX_SERIES);
        if (!seriesKeys.length) {
            return null;
        }
        var labels = rows.map(function (r) {
            var v = r[categoryKey];
            return v === null || v === undefined ? "" : String(v);
        });
        var series = seriesKeys.map(function (key) {
            return {
                key: key,
                values: seriesValues(rows, key),
            };
        });
        var dominantKey = pickDominantMetric(rows, seriesKeys) || seriesKeys[0];
        var temporal =
            (isTimeLikeKey(categoryKey) || isTimeLikeValues(rows, categoryKey)) &&
            labels.length >= 3;
        var pieOk =
            !temporal &&
            labels.length >= 2 &&
            labels.length <= PIE_MAX_CATS &&
            series[0].values.every(function (v) {
                return v >= 0;
            });
        var categoricalPieOk = pieOk;
        var multi = seriesKeys.length >= 2;
        var periodBuckets = seriesKeysArePeriodBuckets(seriesKeys);
        var stackedOk = multi && allSeriesNonNegative(series);
        var horizontalOk = !temporal && labels.length >= 2;
        var radarOk =
            !temporal &&
            labels.length >= RADAR_MIN_CATS &&
            labels.length <= RADAR_MAX_CATS;
        var defaultMode;
        if (multi && periodBuckets && !temporal) {
            defaultMode = "bar";
        } else if (multi) {
            defaultMode = "mix";
        } else {
            defaultMode = temporal ? "line" : "bar";
        }
        return {
            categoryKey: categoryKey,
            seriesKeys: seriesKeys,
            dominantKey: dominantKey,
            labels: labels,
            series: series,
            dualAxis: periodBuckets ? false : needsDualAxis(series),
            temporal: temporal,
            periodBuckets: periodBuckets,
            defaultMode: defaultMode,
            pieOk: categoricalPieOk && seriesKeys.length === 1,
            categoricalPieOk: categoricalPieOk,
            stackedOk: stackedOk,
            horizontalOk: horizontalOk,
            radarOk: radarOk,
        };
    }

    function periodLikeValue(val) {
        var s = String(val === null || val === undefined ? "" : val).trim();
        return s && (isPeriodSeriesKey(s) || TIME_VAL_RE.test(s));
    }

    function tryPivotLongRows(rows) {
        if (!rows || rows.length < 2) {
            return null;
        }
        var keys = columnKeys(rows);
        var numericKeys = keys.filter(function (k) {
            return isNumericColumn(rows, k);
        });
        var textKeys = keys.filter(function (k) {
            return numericKeys.indexOf(k) < 0;
        });
        if (numericKeys.length !== 1 || textKeys.length < 2) {
            return null;
        }
        var valueKey = numericKeys[0];
        var periodKey = null;
        var catKey = null;
        var i;
        for (i = 0; i < textKeys.length; i++) {
            var k = textKeys[i];
            if (isPeriodSeriesKey(k) || isTimeLikeKey(k)) {
                periodKey = k;
                continue;
            }
            var hits = 0;
            var seen = 0;
            var ri;
            for (ri = 0; ri < rows.length && ri < 40; ri++) {
                var v = rows[ri][k];
                if (v === null || v === undefined || v === "") {
                    continue;
                }
                seen++;
                if (periodLikeValue(v)) {
                    hits++;
                }
            }
            if (seen > 0 && hits >= Math.max(1, Math.floor(seen * 0.6))) {
                periodKey = k;
            } else if (!catKey) {
                catKey = k;
            }
        }
        if (!periodKey || !catKey || periodKey === catKey) {
            return null;
        }
        var bucketMap = {};
        var catMap = {};
        rows.forEach(function (r) {
            var cat = r[catKey];
            var per = r[periodKey];
            if (cat === null || cat === undefined || cat === "") {
                return;
            }
            if (per === null || per === undefined || per === "") {
                return;
            }
            var catLabel = String(cat);
            var perLabel = String(per);
            bucketMap[perLabel] = 1;
            if (!catMap[catLabel]) {
                catMap[catLabel] = {};
            }
            var n = parseNumber(r[valueKey]);
            catMap[catLabel][perLabel] = n === null ? 0 : n;
        });
        var buckets = orderPeriodSeriesKeys(Object.keys(bucketMap));
        if (buckets.length < 2) {
            return null;
        }
        var pivoted = Object.keys(catMap).map(function (catLabel) {
            var row = {};
            row[catKey] = catLabel;
            buckets.forEach(function (b) {
                row[b] = catMap[catLabel][b] || 0;
            });
            return row;
        });
        return pivoted.length ? pivoted : null;
    }

    function isPieLikeMode(mode) {
        return mode === "pie" || mode === "donut" || mode === "rose";
    }

    /**
     * Altura del host: más aire vertical en series temporales / multi-serie,
     * y filas altas en barras horizontales. Sin hardcode de dominio.
     * Tarjeta dashboard compacta = más baja; maximizada = misma fórmula que chat.
     */
    function resolveChartHostHeightPx(meta, mode, block) {
        var nLab = meta && meta.labels ? meta.labels.length : 0;
        var nSer = meta && meta.series ? meta.series.length : 1;
        var vh =
            typeof global.innerHeight === "number" && global.innerHeight > 0
                ? global.innerHeight
                : 800;
        var inDash = !!(
            block &&
            block.closest &&
            block.closest(".o_ai_dashboard_card")
        );
        var maximized = !!(
            block &&
            block.closest &&
            block.closest(".o_chatboo_dashboard_card_maximized")
        );

        // Solo las tarjetas compactas del grid se quedan bajas y sin scroll.
        // Maximizada → misma lógica que un gráfico de chat normal.
        if (inDash && !maximized) {
            var body =
                block.closest && block.closest(".o_ai_dashboard_card_body");
            var toolbar = block.querySelector
                ? block.querySelector(".o_ai_chart_toolbar")
                : null;
            var title = block.querySelector
                ? block.querySelector(".o_ai_block_title, .pns-result-title")
                : null;
            var bodyH = body && body.clientHeight > 0 ? body.clientHeight : 0;
            var tbH = toolbar && toolbar.offsetHeight ? toolbar.offsetHeight : 34;
            var titleH =
                title && title.offsetParent !== null ? title.offsetHeight + 6 : 0;
            var avail;
            if (bodyH > 60) {
                // Padding del body (~16) + margen pequeño.
                avail = bodyH - tbH - titleH - 18;
            } else {
                avail = Math.min(200, Math.round(vh * 0.22));
            }
            // Techo bajo: leyenda ECharts va dentro del host; no empujar el body.
            return Math.max(140, Math.min(avail, 210));
        }

        if (isPieLikeMode(mode)) {
            return Math.max(300, Math.min(380, Math.round(vh * 0.42)));
        }
        if (mode === "radar") {
            return Math.max(320, Math.min(420, Math.round(vh * 0.46)));
        }
        if (mode === "bar_h") {
            var rowPx = 30;
            var hBar = 110 + nLab * rowPx;
            return Math.max(300, Math.min(hBar, Math.round(vh * 0.72), 680));
        }

        // Cartesian (barras / líneas / combinado / área / stack).
        var h = 360;
        if (nLab > 6) {
            h += Math.min(140, (nLab - 6) * 12);
        }
        if (nSer > 1) {
            h += Math.min(72, (nSer - 1) * 24);
        }
        if (meta && meta.temporal) {
            h += 28;
        }
        var floor = 340;
        var ceiling = Math.min(640, Math.round(vh * 0.65));
        return Math.max(floor, Math.min(h, ceiling));
    }

    function applyChartHostHeight(host, meta, mode, block) {
        if (!host) {
            return;
        }
        var px = resolveChartHostHeightPx(meta, mode || (meta && meta.defaultMode), block);
        var inDash = !!(
            block &&
            block.closest &&
            block.closest(".o_ai_dashboard_card")
        );
        var maximized = !!(
            block &&
            block.closest &&
            block.closest(".o_chatboo_dashboard_card_maximized")
        );
        host.style.height = px + "px";
        host.style.maxHeight = px + "px";
        // En tarjeta compacta no forzar minHeight alto (provoca scroll del body).
        host.style.minHeight =
            inDash && !maximized
                ? Math.min(px, 140) + "px"
                : Math.min(px, 300) + "px";
        host.setAttribute("data-chatboo-chart-height", String(px));
    }

    /** Recalcula altura (p. ej. al maximizar/restaurar tarjeta) y pide resize. */
    function relayoutChartsIn(root) {
        if (!root || !root.querySelectorAll) {
            return;
        }
        var blocks = root.querySelectorAll(".o_ai_table_block");
        var i;
        for (i = 0; i < blocks.length; i++) {
            var block = blocks[i];
            var meta = block._chatbooChartMeta;
            var host = block.querySelector(".o_ai_chart_host");
            if (!meta || !host) {
                continue;
            }
            var open = block.getAttribute("data-chatboo-chart-open") === "1";
            if (!open && host.style.display === "none") {
                continue;
            }
            applyChartHostHeight(
                host,
                meta,
                block._chatbooChartMode || meta.defaultMode,
                block
            );
            resizeChartToHost(block);
        }
    }

    function normalizeEchartsMode(meta, mode) {
        if (isPieLikeMode(mode) && !meta.categoricalPieOk) {
            return meta.defaultMode;
        }
        if (mode === "stack" && !meta.stackedOk) {
            return meta.defaultMode;
        }
        if (mode === "bar_h" && !meta.horizontalOk) {
            return meta.defaultMode;
        }
        if (mode === "radar" && !meta.radarOk) {
            return meta.defaultMode;
        }
        return mode;
    }

    function chartTypeOptions(engine, meta) {
        var opts = [];
        var multi = meta.series.length >= 2;
        if (engine === ENGINE_ECHARTS) {
            if (multi && meta.periodBuckets) {
                opts.push({ v: "bar", t: "Barras agrupadas" });
                if (meta.stackedOk) {
                    opts.push({ v: "stack", t: "Apilado" });
                }
                opts.push({ v: "mix", t: "Combinado" });
            } else if (multi) {
                opts.push({ v: "mix", t: "Combinado" });
            }
            if (!meta.periodBuckets || !multi) {
                opts.push({ v: "bar", t: "Barras" });
            }
            opts.push({ v: "line", t: "Líneas" });
            if (multi) {
                opts.push({ v: "area", t: "Área" });
            }
            if (meta.stackedOk && !(multi && meta.periodBuckets)) {
                opts.push({ v: "stack", t: "Apilado" });
            }
            if (meta.horizontalOk) {
                opts.push({ v: "bar_h", t: "Horizontal" });
            }
            if (meta.radarOk) {
                opts.push({ v: "radar", t: "Radar" });
            }
            if (meta.categoricalPieOk) {
                opts.push({ v: "donut", t: "Quesito" }, { v: "pie", t: "Tarta" });
                if (meta.labels.length >= 3) {
                    opts.push({ v: "rose", t: "Rosa" });
                }
            }
        } else {
            if (multi) {
                opts.push({ v: "mix", t: "Combinado" });
            }
            opts.push({ v: "bar", t: "Barras" }, { v: "line", t: "Líneas" });
            if (meta.pieOk) {
                opts.push({ v: "pie", t: "Tarta" });
            }
        }
        return opts;
    }

    /** Ciclo corto de rotación (Chart.js / cartesian). */
    function rotateCycle(meta) {
        if (!meta || !meta.series || meta.series.length < 2) {
            return ["bar", "line"];
        }
        return ["mix", "mix_inv", "bar", "line"];
    }

    function rotateCycleForEngine(engine, meta, currentMode) {
        if (engine === ENGINE_ECHARTS) {
            if (isPieLikeMode(currentMode)) {
                var pieCycle = ["donut", "pie"];
                if (meta.labels.length >= 3) {
                    pieCycle.push("rose");
                }
                return pieCycle;
            }
            if (currentMode === "radar") {
                return ["radar"];
            }
            if (!meta.series || meta.series.length < 2) {
                var singleCycle = ["bar", "line", "area"];
                if (meta.horizontalOk) {
                    singleCycle.push("bar_h");
                }
                return singleCycle;
            }
            if (meta.periodBuckets) {
                var periodCycle = ["bar"];
                if (meta.stackedOk) {
                    periodCycle.push("stack");
                }
                periodCycle.push("mix", "line", "area");
                if (meta.horizontalOk) {
                    periodCycle.push("bar_h");
                }
                return periodCycle;
            }
            var multiCycle = ["mix", "mix_inv", "bar", "line", "area"];
            if (meta.stackedOk) {
                multiCycle.push("stack");
            }
            if (meta.horizontalOk) {
                multiCycle.push("bar_h");
            }
            return multiCycle;
        }
        return rotateCycle(meta);
    }

    function rotateControlForEngine(engine, meta, currentMode) {
        if (engine === ENGINE_ECHARTS) {
            if (currentMode === "radar") {
                return { show: false, title: "", icon: "combo" };
            }
            if (isPieLikeMode(currentMode)) {
                return {
                    show: meta.categoricalPieOk,
                    title: "Rotar quesito / tarta / rosa",
                    icon: "pie",
                };
            }
            return {
                show: true,
                title: "Rotar tipo (combinado, apilado, horizontal…)",
                icon: "combo",
            };
        }
        return {
            show: currentMode !== "pie",
            title: "Rotar combinación (barra/línea por serie)",
            icon: "combo",
        };
    }

    /**
     * Tipo por serie: mix = mayor absMax → barra, resto → línea; mix_inv invierte.
     */
    function resolveSeriesTypes(meta, mode) {
        var n = meta.series.length;
        var types = [];
        var i;
        if (mode === "bar" || mode === "stack" || mode === "bar_h") {
            for (i = 0; i < n; i++) {
                types.push("bar");
            }
            return types;
        }
        if (mode === "line") {
            for (i = 0; i < n; i++) {
                types.push("line");
            }
            return types;
        }
        if (mode === "area") {
            for (i = 0; i < n; i++) {
                types.push("line");
            }
            return types;
        }
        var hiType = mode === "mix_inv" ? "line" : "bar";
        var loType = mode === "mix_inv" ? "bar" : "line";
        if (n === 1) {
            types.push(hiType);
            return types;
        }
        var ranked = meta.series.map(function (s, idx) {
            return { idx: idx, m: absMax(s.values) };
        });
        ranked.sort(function (a, b) {
            if (b.m !== a.m) {
                return b.m - a.m;
            }
            return a.idx - b.idx;
        });
        for (i = 0; i < n; i++) {
            types.push(loType);
        }
        types[ranked[0].idx] = hiType;
        // 3 series: la 2ª de mayor escala también barra si no es “pequeña” vs la 1ª.
        if (n >= 3 && ranked.length >= 2) {
            var top = ranked[0].m || 1;
            var mid = ranked[1].m;
            if (mid > 0 && top / mid < SCALE_RATIO_DUAL) {
                types[ranked[1].idx] = hiType;
            }
        }
        return types;
    }

    function selectValueForMode(mode) {
        if (mode === "mix_inv") {
            return "mix";
        }
        if (
            mode === "bar" ||
            mode === "line" ||
            mode === "pie" ||
            mode === "donut" ||
            mode === "rose" ||
            mode === "area" ||
            mode === "stack" ||
            mode === "bar_h" ||
            mode === "radar"
        ) {
            return mode;
        }
        return "mix";
    }

    var MIN_HOST_PX = 64;

    function hostInnerSize(host) {
        if (!host) {
            return { w: 0, h: 0 };
        }
        return {
            w: host.clientWidth || 0,
            h: host.clientHeight || 0,
        };
    }

    function disconnectHostObserver(block) {
        if (block && block._chatbooChartRO) {
            try {
                block._chatbooChartRO.disconnect();
            } catch (e) {
                /* ignore */
            }
            block._chatbooChartRO = null;
        }
    }

    /**
     * Chart.js/ECharts, si nació con host 0×0, dejan el surface en unos px.
     * resize() sin args relee ese box; hay que pasar el tamaño del host.
     */
    function resizeChartToHost(block) {
        var host =
            block && block.querySelector
                ? block.querySelector(".o_ai_chart_host")
                : null;
        var chart = block && block._chatbooChart;
        if (!host || !chart || typeof chart.resize !== "function") {
            return false;
        }
        var size = hostInnerSize(host);
        if (size.w < MIN_HOST_PX || size.h < MIN_HOST_PX) {
            return false;
        }
        try {
            if (block._chatbooChartEngine === ENGINE_ECHARTS) {
                chart.resize({ width: size.w, height: size.h });
            } else {
                var canvas = chart.canvas;
                if (canvas) {
                    canvas.style.width = "";
                    canvas.style.height = "";
                }
                chart.resize(size.w, size.h);
            }
            return true;
        } catch (e) {
            return false;
        }
    }

    function observeChartHost(block) {
        disconnectHostObserver(block);
        var host = block && block.querySelector
            ? block.querySelector(".o_ai_chart_host")
            : null;
        if (!host || typeof global.ResizeObserver === "undefined") {
            return;
        }
        var ticking = false;
        var ro = new global.ResizeObserver(function () {
            if (ticking) {
                return;
            }
            ticking = true;
            var kick = function () {
                ticking = false;
                if (block._chatbooChartLaidOut) {
                    resizeChartToHost(block);
                } else {
                    relayoutChart(block);
                }
            };
            global.requestAnimationFrame(kick);
        });
        try {
            ro.observe(host);
            block._chatbooChartRO = ro;
        } catch (e) {
            try {
                ro.disconnect();
            } catch (e2) {
                /* ignore */
            }
        }
    }

    function destroyChart(block) {
        disconnectHostObserver(block);
        if (block._chatbooChartResize) {
            try {
                global.removeEventListener("resize", block._chatbooChartResize);
            } catch (e) {
                /* ignore */
            }
            block._chatbooChartResize = null;
        }
        if (block._chatbooChart) {
            try {
                if (block._chatbooChartEngine === ENGINE_ECHARTS) {
                    block._chatbooChart.dispose();
                } else {
                    block._chatbooChart.destroy();
                }
            } catch (e) {
                /* ignore */
            }
            block._chatbooChart = null;
            block._chatbooChartEngine = null;
        }
    }

    function chartColors(n) {
        var palette = [
            "rgba(13, 110, 253, 0.75)",
            "rgba(25, 135, 84, 0.75)",
            "rgba(253, 126, 20, 0.75)",
            "rgba(111, 66, 193, 0.75)",
            "rgba(214, 51, 132, 0.75)",
            "rgba(32, 201, 151, 0.75)",
            "rgba(13, 202, 240, 0.75)",
            "rgba(108, 117, 125, 0.75)",
        ];
        var out = [];
        for (var i = 0; i < n; i++) {
            out.push(palette[i % palette.length]);
        }
        return out;
    }

    function formatTick(value) {
        if (typeof value !== "number" || !isFinite(value)) {
            return value;
        }
        try {
            return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
        } catch (e) {
            return String(value);
        }
    }

    function buildChartConfig(meta, mode) {
        var colors = chartColors(Math.max(meta.series.length, meta.labels.length));
        if (mode === "pie") {
            return {
                type: "pie",
                data: {
                    labels: meta.labels,
                    datasets: [
                        {
                            label: humanizeKey(meta.seriesKeys[0]),
                            data: meta.series[0].values,
                            backgroundColor: colors.slice(0, meta.labels.length),
                            borderWidth: 1,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    resizeDelay: 0,
                    plugins: {
                        legend: { position: "bottom" },
                        title: {
                            display: true,
                            text: humanizeKey(meta.seriesKeys[0]),
                            font: { size: 12 },
                        },
                    },
                },
            };
        }

        var seriesTypes = resolveSeriesTypes(meta, mode);
        // Chart.js 4: si el tipo raíz es "line", las barras del dataset casi no se ven.
        // Raíz = bar si hay alguna barra; si no, line.
        var hasBar = seriesTypes.indexOf("bar") >= 0;
        var rootType = hasBar ? "bar" : "line";

        var xTitle = humanizeKey(meta.categoryKey);
        var axisIds = resolveAxisIds(meta);
        var titles = resolveYTitles(meta, axisIds);
        var yTitle = titles.yTitle;
        var y1Title = titles.y1Title;
        var useY1 = titles.useY1;
        var scales = {
            x: {
                title: {
                    display: !!xTitle,
                    text: xTitle,
                    font: { size: 12, weight: "500" },
                },
                ticks: { maxRotation: 45, minRotation: 0 },
            },
            y: {
                type: "linear",
                display: true,
                beginAtZero: true,
                position: "left",
                title: {
                    display: !!yTitle,
                    text: yTitle,
                    font: { size: 12, weight: "500" },
                },
                ticks: {
                    callback: formatTick,
                },
            },
        };
        if (useY1) {
            scales.y1 = {
                type: "linear",
                display: true,
                beginAtZero: true,
                position: "right",
                grid: { drawOnChartArea: false },
                title: {
                    display: !!y1Title,
                    text: y1Title,
                    font: { size: 12, weight: "500" },
                },
                ticks: {
                    callback: formatTick,
                },
            };
        }

        var datasets = meta.series.map(function (s, idx) {
            var dsType = seriesTypes[idx] || "bar";
            var border = colors[idx].replace("0.75", "1");
            var isLine = dsType === "line";
            return {
                type: dsType,
                label: humanizeKey(s.key),
                data: s.values.slice(),
                backgroundColor: isLine ? border : colors[idx],
                borderColor: border,
                borderWidth: isLine ? 2 : 1,
                fill: false,
                tension: isLine ? 0.25 : 0,
                pointRadius: isLine ? 3 : 0,
                pointHoverRadius: isLine ? 5 : 0,
                yAxisID: axisIds[idx],
                // Menor order = delante; barras detrás de líneas.
                order: isLine ? 1 : 2,
            };
        });

        return {
            type: rootType,
            data: {
                labels: meta.labels,
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                resizeDelay: 0,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        display: meta.series.length > 1,
                        position: "bottom",
                    },
                },
                scales: scales,
            },
        };
    }

    function extremeScaleGap(a, b) {
        var hi = Math.max(a, b);
        var lo = Math.min(a, b);
        return lo > 0 && hi / lo >= SCALE_RATIO_DUAL_EXTREME;
    }

    /**
     * Dual Y: dominante + series de la misma magnitud → izquierda;
     * ratios / contadores (forma de clave) / hueco de escala extremo → derecha.
     * Invariante: no empujar a y1 toda serie no-dominante (aplasta la pequeña
     * cuando comparte eje con otra de magnitud alta).
     */
    function resolveAxisIds(meta) {
        if (!meta.dualAxis) {
            return meta.series.map(function () {
                return "y";
            });
        }
        var dom = null;
        var i;
        if (meta.dominantKey) {
            for (i = 0; i < meta.series.length; i++) {
                if (meta.series[i].key === meta.dominantKey) {
                    dom = meta.series[i];
                    break;
                }
            }
        }
        if (!dom) {
            dom = meta.series.length ? meta.series[0] : null;
        }
        var domMax = dom ? absMax(dom.values) || 1 : 1;
        var domIsCount = dom ? isCountLikeKey(dom.key) : false;
        return meta.series.map(function (s) {
            if (dom && s.key === dom.key) {
                return "y";
            }
            if (isRatioLikeKey(s.key)) {
                return "y1";
            }
            if (isCountLikeKey(s.key) && !domIsCount) {
                return "y1";
            }
            if (!isCountLikeKey(s.key) && domIsCount) {
                return "y1";
            }
            var m = absMax(s.values);
            if (m > 0 && extremeScaleGap(domMax, m)) {
                return "y1";
            }
            return "y";
        });
    }

    function resolveYTitles(meta, axisIds) {
        var xTitle = humanizeKey(meta.categoryKey);
        var yTitle = humanizeKey(meta.dominantKey || meta.seriesKeys[0]);
        var useY1 = axisIds.indexOf("y1") >= 0;
        var y1Title = meta.series
            .filter(function (_s, idx) {
                return axisIds[idx] === "y1";
            })
            .map(function (s) {
                return humanizeKey(s.key);
            })
            .join(" · ");
        var yLeftKeys = meta.series
            .filter(function (_s, idx) {
                return axisIds[idx] === "y";
            })
            .map(function (s) {
                return humanizeKey(s.key);
            });
        if (yLeftKeys.length > 1) {
            yTitle = yLeftKeys.join(" · ");
        }
        return { xTitle: xTitle, yTitle: yTitle, y1Title: y1Title, useY1: useY1 };
    }

    function dsTypePointer(seriesTypes) {
        var hasBar = false;
        var hasLine = false;
        var i;
        for (i = 0; i < seriesTypes.length; i++) {
            if (seriesTypes[i] === "bar") {
                hasBar = true;
            }
            if (seriesTypes[i] === "line") {
                hasLine = true;
            }
        }
        if (hasBar && hasLine) {
            return "cross";
        }
        return hasLine ? "line" : "shadow";
    }

    function pieSeriesIndex(meta) {
        var best = 0;
        var bestM = -1;
        var i;
        for (i = 0; i < meta.series.length; i++) {
            var m = absMax(meta.series[i].values);
            if (m > bestM) {
                bestM = m;
                best = i;
            }
        }
        return best;
    }

    function buildEchartsPieOption(meta, mode) {
        var colors = chartColors(Math.max(meta.series.length, meta.labels.length));
        var sIdx = pieSeriesIndex(meta);
        var seriesKey = meta.seriesKeys[sIdx];
        var pieData = meta.labels.map(function (label, idx) {
            return {
                name: label,
                value: meta.series[sIdx].values[idx],
            };
        });
        var radius;
        var roseType;
        if (mode === "donut") {
            radius = ["38%", "62%"];
        } else if (mode === "rose") {
            radius = ["10%", "62%"];
            roseType = "radius";
        } else {
            radius = ["0%", "62%"];
        }
        var pieSeries = {
            type: "pie",
            radius: radius,
            center: ["50%", "48%"],
            data: pieData,
            emphasis: {
                itemStyle: {
                    shadowBlur: 8,
                    shadowOffsetX: 0,
                    shadowColor: "rgba(0,0,0,0.18)",
                },
            },
        };
        if (roseType) {
            pieSeries.roseType = roseType;
        }
        return {
            color: colors,
            title: {
                text: humanizeKey(seriesKey),
                left: "center",
                top: 4,
                textStyle: { fontSize: 12, fontWeight: "500" },
            },
            tooltip: { trigger: "item", valueFormatter: formatTick },
            legend: { bottom: 0, type: "scroll" },
            series: [pieSeries],
        };
    }

    function buildEchartsRadarOption(meta) {
        var colors = chartColors(meta.series.length);
        var indicators = meta.labels.map(function (label, idx) {
            var m = 0;
            var si;
            for (si = 0; si < meta.series.length; si++) {
                m = Math.max(m, meta.series[si].values[idx] || 0);
            }
            return {
                name: label,
                max: m > 0 ? m * 1.15 : 1,
            };
        });
        return {
            color: colors,
            tooltip: { trigger: "item", valueFormatter: formatTick },
            legend: {
                show: meta.series.length > 1,
                bottom: 0,
                type: "scroll",
            },
            radar: {
                indicator: indicators,
                center: ["50%", "52%"],
                radius: "62%",
            },
            series: [
                {
                    type: "radar",
                    data: meta.series.map(function (s) {
                        return {
                            name: humanizeKey(s.key),
                            value: s.values.slice(),
                        };
                    }),
                },
            ],
        };
    }

    function buildEchartsCartesianOption(meta, mode) {
        var colors = chartColors(Math.max(meta.series.length, meta.labels.length));
        var horizontal = mode === "bar_h";
        var stacked = mode === "stack";
        var cartMode = stacked || horizontal ? "bar" : mode;
        var seriesTypes = resolveSeriesTypes(meta, cartMode);
        var useDual = meta.dualAxis && !stacked && !horizontal;
        var axisIds = useDual
            ? resolveAxisIds(meta)
            : meta.series.map(function () {
                  return "y";
              });
        var titles = resolveYTitles(meta, axisIds);
        var yAxis = [
            {
                type: "value",
                name: titles.yTitle,
                nameTextStyle: { fontSize: 12, fontWeight: "500" },
                axisLabel: { formatter: formatTick },
            },
        ];
        if (titles.useY1 && useDual) {
            yAxis.push({
                type: "value",
                name: titles.y1Title,
                nameTextStyle: { fontSize: 12, fontWeight: "500" },
                axisLabel: { formatter: formatTick },
                splitLine: { show: false },
            });
        }

        var series = meta.series.map(function (s, idx) {
            var dsType = seriesTypes[idx] === "line" ? "line" : "bar";
            var border = colors[idx].replace("0.75", "1");
            var yIdx = titles.useY1 && useDual && axisIds[idx] === "y1" ? 1 : 0;
            var item = {
                name: humanizeKey(s.key),
                type: dsType,
                data: s.values.slice(),
                yAxisIndex: horizontal ? 0 : yIdx,
                xAxisIndex: 0,
                emphasis: { focus: "series" },
            };
            if (stacked && dsType === "bar") {
                item.stack = "total";
            }
            if (dsType === "line") {
                item.smooth = 0.25;
                item.symbolSize = 6;
                item.lineStyle = { width: 2, color: border };
                item.itemStyle = { color: border };
                if (mode === "area") {
                    item.areaStyle = { opacity: 0.25, color: colors[idx] };
                }
            } else {
                item.itemStyle = { color: colors[idx] };
            }
            return item;
        });

        var xLabel = categoryAxisLabel(meta.labels);
        // containLabel already rooms rotated ticks; only reserve the legend strip.
        var legendBottom = meta.series.length > 1 ? 28 : 8;
        var common = {
            color: colors,
            tooltip: {
                trigger: "axis",
                axisPointer: { type: dsTypePointer(seriesTypes) },
            },
            legend: {
                show: meta.series.length > 1,
                bottom: 0,
                type: "scroll",
            },
            series: series,
        };

        if (horizontal) {
            return Object.assign({}, common, {
                grid: {
                    left: "3%",
                    right: "4%",
                    top: 28,
                    bottom: legendBottom,
                    containLabel: true,
                },
                xAxis: {
                    type: "value",
                    axisLabel: { formatter: formatTick },
                },
                yAxis: {
                    type: "category",
                    data: meta.labels.slice().reverse(),
                    name: titles.xTitle,
                    nameTextStyle: { fontSize: 12, fontWeight: "500" },
                    axisLabel: {
                        width: 96,
                        overflow: "truncate",
                    },
                },
            });
        }

        return Object.assign({}, common, {
            grid: {
                left: "3%",
                right: titles.useY1 && useDual ? "6%" : "3%",
                top: 28,
                bottom: legendBottom,
                containLabel: true,
            },
            xAxis: {
                type: "category",
                data: meta.labels,
                name: titles.xTitle,
                nameTextStyle: { fontSize: 12, fontWeight: "500" },
                axisLabel: xLabel,
            },
            yAxis: yAxis,
        });
    }

    function buildEchartsOption(meta, mode) {
        if (isPieLikeMode(mode)) {
            return buildEchartsPieOption(meta, mode);
        }
        if (mode === "radar") {
            return buildEchartsRadarOption(meta);
        }
        return buildEchartsCartesianOption(meta, mode);
    }

    function blockChartEngine(block) {
        var raw = (block.getAttribute("data-ai-chart-engine") || "").toLowerCase();
        if (!raw && global.CHATBOO_CHART_ENGINE) {
            raw = String(global.CHATBOO_CHART_ENGINE).toLowerCase();
        }
        if (raw === ENGINE_ECHARTS && EchartsLib) {
            return ENGINE_ECHARTS;
        }
        if (raw === ENGINE_CHARTJS && typeof ChartLib === "function") {
            return ENGINE_CHARTJS;
        }
        if (!raw || raw === ENGINE_ECHARTS) {
            if (typeof ChartLib === "function") {
                return ENGINE_CHARTJS;
            }
            if (EchartsLib) {
                return ENGINE_ECHARTS;
            }
        }
        return null;
    }

    function blockShowMode(block) {
        var sm = (
            block.getAttribute("data-ai-show-mode")
            || SHOW_MODE_TABLE_CHART
        ).toLowerCase();
        if (sm === "table-chart") {
            sm = SHOW_MODE_TABLE_CHART;
        } else if (sm === "chart-table") {
            sm = SHOW_MODE_CHART_TABLE;
        }
        if (sm === SHOW_MODE_TABLE_ONLY) {
            return SHOW_MODE_TABLE_ONLY;
        }
        return sm === SHOW_MODE_CHART_TABLE ? SHOW_MODE_CHART_TABLE : SHOW_MODE_TABLE_CHART;
    }

    function chartsAllowedForBlock(block) {
        // Explicit table-only, or ancestor marked no-charts (skill opt-out).
        // Report mode does NOT ban charts — the LLM may embed native ones.
        if (blockShowMode(block) === SHOW_MODE_TABLE_ONLY) {
            return false;
        }
        if (block.closest) {
            var banned = block.closest("[data-chatboo-no-charts='1']");
            if (banned) {
                return false;
            }
        }
        return true;
    }

    function isChartTableMode(block) {
        return blockShowMode(block) === SHOW_MODE_CHART_TABLE;
    }

    function tableWraps(block) {
        return block.querySelectorAll(".table-responsive");
    }

    function setTableCollapsed(block, collapsed) {
        var wraps = tableWraps(block);
        var i;
        for (i = 0; i < wraps.length; i++) {
            if (collapsed) {
                wraps[i].classList.add("o_chatboo_table_collapsed");
            } else {
                wraps[i].classList.remove("o_chatboo_table_collapsed");
            }
        }
        block.setAttribute("data-chatboo-table-collapsed", collapsed ? "1" : "0");
    }

    /** One view at a time: the button names the other one. */
    function updatePrimaryToggleLabel(block) {
        var open = block.getAttribute("data-chatboo-chart-open") === "1";
        var controls = block.querySelector(".o_chatboo_chart_controls");
        if (controls) {
            controls.style.display = open ? "" : "none";
        }
        var btn = block.querySelector(".o_chatboo_chart_toggle");
        if (!btn) {
            return;
        }
        btn.textContent = open ? label("data") : label("chart");
        btn.setAttribute("aria-pressed", "false");
    }

    function showChartView(block, meta, mode) {
        renderChart(block, meta, mode);
        if (block.getAttribute("data-chatboo-chart-open") === "1") {
            setTableCollapsed(block, true);
        }
        updatePrimaryToggleLabel(block);
    }

    function showTableView(block) {
        hideChart(block);
        setTableCollapsed(block, false);
        updatePrimaryToggleLabel(block);
    }

    function prepareChartSurface(host, engine) {
        host.innerHTML = "";
        if (engine === ENGINE_ECHARTS) {
            var div = document.createElement("div");
            div.className = "o_ai_echarts_surface";
            div.style.width = "100%";
            div.style.height = "100%";
            host.appendChild(div);
            return div;
        }
        var canvas = document.createElement("canvas");
        host.appendChild(canvas);
        return canvas;
    }

    function syncSelect(select, mode) {
        if (!select) {
            return;
        }
        var v = selectValueForMode(mode);
        if (select.querySelector('option[value="' + v + '"]')) {
            select.value = v;
        }
    }

    function fillTypeSelect(select, engine, meta, selectedMode) {
        if (!select) {
            return;
        }
        var prev = selectedMode || select.value;
        select.innerHTML = "";
        chartTypeOptions(engine, meta).forEach(function (o) {
            var opt = document.createElement("option");
            opt.value = o.v;
            opt.textContent = o.t;
            select.appendChild(opt);
        });
        syncSelect(select, prev || meta.defaultMode);
    }

    function syncRotateControl(block, meta, mode) {
        var rot = block.querySelector(".o_chatboo_chart_rotate");
        if (!rot) {
            return;
        }
        var engine =
            block._chatbooChartEngine || blockChartEngine(block) || ENGINE_CHARTJS;
        var ctrl = rotateControlForEngine(engine, meta, mode);
        rot.style.display = ctrl.show ? "" : "none";
        rot.disabled = !ctrl.show;
        rot.setAttribute("title", ctrl.title);
        rot.setAttribute("aria-label", ctrl.title);
        rot.innerHTML = ctrl.icon === "pie" ? pieSvg() : rotateSvg();
    }

    function shouldExpandChartCanvas(block) {
        if (isChartTableMode(block)) {
            return true;
        }
        return block.getAttribute("data-chatboo-chart-open") === "1";
    }

    /** Marca la burbuja del turno; el ancho lo pone --o-chatboo-card-width (2/3). */
    function expandChartMessageCanvas(block) {
        if (!block || !shouldExpandChartCanvas(block)) {
            return;
        }
        var bubble = block.closest(".o_chatboo_message, .o_chatboo_bubble");
        if (bubble && !bubble.classList.contains("o_chatboo_message--dashboard")) {
            bubble.classList.add("o_chatboo_message--chart");
            bubble.style.removeProperty("width");
            bubble.style.removeProperty("max-width");
        }
        var row = block.closest(".d-flex");
        if (row && !row.classList.contains("o_chatboo_message_row--dashboard")) {
            row.classList.add("o_chatboo_message_row--chart");
            row.style.width = "100%";
            row.style.maxWidth = "100%";
        }
    }

    /**
     * Height and engine size from the host as laid out now. A host with no
     * width yet (hidden overlay, card not placed) is measured again by the
     * ResizeObserver when it gets one.
     */
    function relayoutChart(block) {
        var host = block.querySelector(".o_ai_chart_host");
        var meta = block._chatbooChartMeta;
        if (host && meta) {
            block._chatbooChartLaidOut = hostInnerSize(host).w >= MIN_HOST_PX;
            applyChartHostHeight(
                host,
                meta,
                block._chatbooChartMode || meta.defaultMode,
                block
            );
        }
        resizeChartToHost(block);
    }

    /** Solo resize del motor; no cambia altura del host (evita bucles de RO). */
    function softResizeChartsIn(root) {
        if (!root || !root.querySelectorAll) {
            return;
        }
        var blocks = root.querySelectorAll(".o_ai_table_block");
        var i;
        for (i = 0; i < blocks.length; i++) {
            resizeChartToHost(blocks[i]);
        }
    }

    function headerCellLabel(th) {
        if (!th) {
            return "";
        }
        var t = (th.textContent || "").replace(/[↕▲▼]/g, "");
        return t.replace(/\s+/g, " ").trim();
    }

    function tableCategoryColumnIndex(table, categoryKey) {
        if (!table || !categoryKey) {
            return -1;
        }
        var ths = table.querySelectorAll("thead tr:last-child th");
        var want = String(categoryKey).replace(/\s+/g, " ").trim();
        var i;
        for (i = 0; i < ths.length; i++) {
            if (ths[i].closest && ths[i].closest("tr.o_ai_ficha_title")) {
                continue;
            }
            if (headerCellLabel(ths[i]) === want) {
                return i;
            }
        }
        return -1;
    }

    function rowsInVisibleTableOrder(block, rows, categoryKey) {
        if (!block || !rows || !rows.length || !categoryKey) {
            return rows;
        }
        var table = block.querySelector("table.o_ai_data_table");
        if (!table || !table.tBodies || !table.tBodies[0]) {
            return rows;
        }
        var col = tableCategoryColumnIndex(table, categoryKey);
        if (col < 0) {
            return rows;
        }
        var leftover = rows.slice();
        var out = [];
        var trs = table.tBodies[0].rows;
        var i;
        var j;
        for (i = 0; i < trs.length; i++) {
            var cell = trs[i].cells[col];
            if (!cell) {
                continue;
            }
            var label = cell.getAttribute("data-ai-sort");
            if (label == null || label === "") {
                label = (cell.textContent || "").trim();
            }
            label = String(label);
            for (j = 0; j < leftover.length; j++) {
                var v = leftover[j][categoryKey];
                var s = v === null || v === undefined ? "" : String(v);
                if (s === label) {
                    out.push(leftover[j]);
                    leftover.splice(j, 1);
                    break;
                }
            }
        }
        if (!out.length) {
            return rows;
        }
        return out.concat(leftover);
    }

    function rowsForChart(rows) {
        if (!Array.isArray(rows)) {
            return [];
        }
        return rows.filter(function (r) { return !(r && r._tfoot); });
    }

    function applyVisibleRowOrder(block, meta) {
        if (!meta || !meta.categoryKey || !meta.seriesKeys || !meta.seriesKeys.length) {
            return meta;
        }
        var raw =
            block && block.getAttribute && block.getAttribute("data-ai-dataset");
        if (!raw) {
            return meta;
        }
        var rows;
        try {
            rows = JSON.parse(raw);
        } catch (e) {
            return meta;
        }
        if (!Array.isArray(rows) || !rows.length) {
            return meta;
        }
        rows = rowsForChart(rows);
        if (!rows.length) {
            return meta;
        }
        var ordered = rowsInVisibleTableOrder(block, rows, meta.categoryKey);
        var next = {};
        var k;
        for (k in meta) {
            if (Object.prototype.hasOwnProperty.call(meta, k)) {
                next[k] = meta[k];
            }
        }
        next.labels = ordered.map(function (r) {
            var v = r[meta.categoryKey];
            return v === null || v === undefined ? "" : String(v);
        });
        next.series = meta.seriesKeys.map(function (key) {
            return {
                key: key,
                values: seriesValues(ordered, key),
            };
        });
        return next;
    }

    function renderChart(block, meta, mode) {
        var engine = blockChartEngine(block);
        if (!engine) {
            return;
        }
        meta = applyVisibleRowOrder(block, meta);
        expandChartMessageCanvas(block);
        var host = block.querySelector(".o_ai_chart_host");
        if (!host) {
            return;
        }
        if (engine === ENGINE_CHARTJS && mode === "pie" && !meta.pieOk) {
            mode = meta.defaultMode;
        }
        if (engine === ENGINE_ECHARTS) {
            mode = normalizeEchartsMode(meta, mode || meta.defaultMode);
        }
        if (!mode) {
            mode = meta.defaultMode;
        }
        // Host visible ANTES de init: si está display:none, ECharts/Chart.js
        // miden 0×0 y el primer frame sale aplastado ("burruño").
        applyChartHostHeight(host, meta, mode, block);
        host.style.display = "";
        void host.offsetHeight;
        destroyChart(block);
        var surface = prepareChartSurface(host, engine);
        block._chatbooChartMode = mode;
        block._chatbooChartEngine = engine;
        block._chatbooChartMeta = meta;
        var size = hostInnerSize(host);
        if (engine === ENGINE_ECHARTS) {
            var echartsInit =
                size.w >= MIN_HOST_PX && size.h >= MIN_HOST_PX
                    ? { width: size.w, height: size.h }
                    : undefined;
            block._chatbooChart = EchartsLib.init(surface, null, echartsInit);
            block._chatbooChart.setOption(buildEchartsOption(meta, mode), true);
            block._chatbooChartResize = function () {
                resizeChartToHost(block);
            };
            global.addEventListener("resize", block._chatbooChartResize);
        } else {
            block._chatbooChart = new ChartLib(
                surface.getContext("2d"),
                buildChartConfig(meta, mode)
            );
        }
        block.setAttribute("data-chatboo-chart-open", "1");
        block.setAttribute("data-chatboo-chart-engine-active", engine);
        updatePrimaryToggleLabel(block);
        fillTypeSelect(
            block.querySelector(".o_chatboo_chart_type"),
            engine,
            meta,
            mode
        );
        syncRotateControl(block, meta, mode);
        observeChartHost(block);
        relayoutChart(block);
    }

    function hideChart(block) {
        destroyChart(block);
        var host = block.querySelector(".o_ai_chart_host");
        if (host) {
            host.style.display = "none";
        }
        block.removeAttribute("data-chatboo-chart-open");
        updatePrimaryToggleLabel(block);
    }

    function rotateSvg() {
        // Icono tipo “combo chart”: barras + línea (Material-ish).
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" ' +
            'viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
            '<path fill="currentColor" d="M3 3v18h18v-2H5V3H3zm4 14h2V9H7v8zm4 0h2V5h-2v12zm4 0h2v-6h-2v6z"/>' +
            '<path fill="currentColor" d="M7.5 11.5l3.2-3.5 2.8 2.2 4-5.2.9.7-4.8 6.3-2.7-2.1-2.5 2.7z"/>' +
            "</svg>"
        );
    }

    function pieSvg() {
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" ' +
            'viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
            '<path fill="currentColor" d="M12 2a10 10 0 0 0-8.66 5h17.32A10 10 0 0 0 12 2zm-8.66 7A10 10 0 0 0 12 22V12H3.34z"/>' +
            "</svg>"
        );
    }

    function syncAxisToggle(block, meta) {
        var btn = block.querySelector(".o_chatboo_chart_axis");
        if (!btn) {
            return;
        }
        var multi = meta && meta.series && meta.series.length >= 2 && !meta.periodBuckets;
        btn.style.display = multi ? "" : "none";
        btn.disabled = !multi;
        if (!multi) {
            return;
        }
        var dual = !!meta.dualAxis;
        btn.textContent = dual ? "1 eje Y" : "2 ejes Y";
        btn.setAttribute(
            "title",
            dual
                ? "Usar un solo eje Y (misma escala para todas las series)"
                : "Usar dos ejes Y (útil si mezclas € y %)"
        );
        btn.setAttribute("aria-pressed", dual ? "true" : "false");
        btn.setAttribute("aria-label", btn.getAttribute("title"));
    }

    function mountToolbar(block, meta) {
        if (block.querySelector(".o_chatboo_chart_toggle")) {
            return;
        }
        applyDualAxisOverride(meta, block);
        block._chatbooChartMode = meta.defaultMode;
        block._chatbooChartMeta = meta;
        var engine = blockChartEngine(block) || ENGINE_CHARTJS;

        // The Canvas button may have opened the bar already.
        var toolbar = ownToolbar(block);
        if (toolbar) {
            toolbar.classList.remove("o_chatboo_canvas_bar");
            toolbar.remove();
        } else {
            toolbar = document.createElement("div");
            toolbar.className = "o_ai_chart_toolbar o_ai_noexport";
        }
        toolbar.setAttribute("data-engine", engine);

        var toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "btn btn-sm o_chatboo_chart_toggle";
        toggle.textContent = label("chart");
        toggle.setAttribute("aria-pressed", "false");

        var controls = document.createElement("span");
        controls.className = "o_chatboo_chart_controls";
        controls.style.display = "none";

        var select = document.createElement("select");
        select.className = "form-select form-select-sm o_chatboo_chart_type";
        select.setAttribute("aria-label", "Tipo de gráfico");
        fillTypeSelect(select, engine, meta, meta.defaultMode);

        var rotate = document.createElement("button");
        rotate.type = "button";
        rotate.className = "btn btn-sm o_chatboo_chart_rotate";
        rotate.innerHTML = rotateSvg();

        var axisBtn = document.createElement("button");
        axisBtn.type = "button";
        axisBtn.className = "btn btn-sm o_chatboo_chart_axis";

        var host = document.createElement("div");
        host.className = "o_ai_chart_host";
        host.style.display = "none";

        function currentMode() {
            return block._chatbooChartMode || meta.defaultMode;
        }

        function currentMeta() {
            return block._chatbooChartMeta || meta;
        }

        toggle.addEventListener("click", function () {
            if (block.getAttribute("data-chatboo-chart-open") === "1") {
                showTableView(block);
            } else {
                showChartView(block, currentMeta(), currentMode());
            }
        });
        select.addEventListener("change", function () {
            var v = select.value || meta.defaultMode;
            // "mix" en el selector = combinado default (no invertido).
            var mode = v === "mix" ? "mix" : v;
            if (block.getAttribute("data-chatboo-chart-open") === "1") {
                renderChart(block, currentMeta(), mode);
            } else {
                block._chatbooChartMode = mode;
            }
        });
        rotate.addEventListener("click", function () {
            var eng = blockChartEngine(block) || ENGINE_CHARTJS;
            var m = currentMeta();
            var cycle = rotateCycleForEngine(eng, m, currentMode());
            var cur = currentMode();
            var idx = cycle.indexOf(cur);
            if (idx < 0) {
                idx = cycle.indexOf(selectValueForMode(cur));
            }
            if (idx < 0) {
                idx = 0;
            }
            var next = cycle[(idx + 1) % cycle.length];
            if (block.getAttribute("data-chatboo-chart-open") === "1") {
                renderChart(block, m, next);
            } else {
                block._chatbooChartMode = next;
                syncSelect(select, next);
                syncRotateControl(block, m, next);
            }
        });
        axisBtn.addEventListener("click", function () {
            var m = currentMeta();
            if (!m || m.series.length < 2 || m.periodBuckets) {
                return;
            }
            m.dualAxis = !m.dualAxis;
            block._chatbooDualAxisForce = m.dualAxis;
            block.setAttribute("data-ai-dual-axis", m.dualAxis ? "1" : "0");
            syncAxisToggle(block, m);
            if (block.getAttribute("data-chatboo-chart-open") === "1") {
                renderChart(block, m, currentMode());
            }
        });

        syncRotateControl(block, meta, meta.defaultMode);
        syncAxisToggle(block, meta);

        controls.appendChild(select);
        controls.appendChild(rotate);
        controls.appendChild(axisBtn);
        toolbar.appendChild(toggle);
        toolbar.appendChild(controls);
        // Title and table (or the chart) first. The buttons stay under them.
        block.appendChild(host);
        block.appendChild(toolbar);
    }

    function categoryAxisIsTemporal(meta, rows) {
        if (!meta || !meta.categoryKey) {
            return false;
        }
        if (meta.temporal) {
            return true;
        }
        return (
            isTimeLikeKey(meta.categoryKey) ||
            isTimeLikeValues(rows, meta.categoryKey)
        );
    }

    function shouldOfferChart(block, meta, rows) {
        // show-chart / explicit graphic request → any numeric series
        // (even absurd — user asked).
        if (isChartTableMode(block)) {
            return true;
        }
        // show-table: the Chart button only for money / % / count Y. X may
        // be time or a short category list (areas, codes). CP / coords stay
        // out via key shape.
        if (!meta || !meta.seriesKeys || !meta.seriesKeys.length) {
            return false;
        }
        return meta.seriesKeys.some(isChartMetricKey);
    }

    function mountToolbarOrFallback(block, meta) {
        mountToolbar(block, meta);
        if (isChartTableMode(block)) {
            showChartView(block, meta, meta.defaultMode);
        }
        if (showSeriesStats) {
            mountSeriesStats(block, meta);
        }
    }

    function _t(msgid) {
        if (global.odoo && typeof global.odoo._t === "function") {
            return global.odoo._t(msgid);
        }
        return msgid;
    }

    function computeSeriesStats(values) {
        var nums = [];
        var i;
        for (i = 0; i < (values || []).length; i++) {
            var v = values[i];
            if (typeof v === "number" && isFinite(v)) {
                nums.push(v);
            }
        }
        if (!nums.length) {
            return null;
        }
        nums.sort(function (a, b) { return a - b; });
        var n = nums.length;
        var sum = 0;
        for (i = 0; i < n; i++) {
            sum += nums[i];
        }
        var mean = sum / n;
        var mid = Math.floor(n / 2);
        var median = n % 2 ? nums[mid] : (nums[mid - 1] + nums[mid]) / 2;
        var varSum = 0;
        for (i = 0; i < n; i++) {
            varSum += (nums[i] - mean) * (nums[i] - mean);
        }
        return {
            n: n,
            min: nums[0],
            max: nums[n - 1],
            mean: mean,
            median: median,
            stdev: n > 1 ? Math.sqrt(varSum / (n - 1)) : 0,
            sum: sum,
        };
    }

    function seriesStatsModel(meta) {
        var out = [];
        var series = (meta && meta.series) || [];
        var i;
        for (i = 0; i < series.length; i++) {
            var st = computeSeriesStats(series[i].values);
            if (st) {
                out.push({
                    name: series[i].key || series[i].name || "",
                    stats: st,
                });
            }
        }
        return out;
    }

    function formatStatNumber(v) {
        if (typeof v !== "number" || !isFinite(v)) {
            return "";
        }
        if (Math.abs(v - Math.round(v)) < 1e-9 && Math.abs(v) < 1e12) {
            return String(Math.round(v));
        }
        return String(Math.round(v * 100) / 100);
    }

    function escapeText(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function statsTableHtml(meta) {
        var model = seriesStatsModel(meta);
        if (!model.length) {
            return "";
        }
        var labels = {
            title: _t("Statistics"),
            n: _t("n"),
            min: _t("Min"),
            max: _t("Max"),
            mean: _t("Mean"),
            median: _t("Median"),
            stdev: _t("Std. dev."),
            sum: _t("Sum"),
        };
        var html = '<div class="o_chatboo_series_stats"><table><caption>'
            + labels.title + "</caption><thead><tr><th></th>";
        var keys = ["n", "min", "max", "mean", "median", "stdev", "sum"];
        var i;
        var j;
        for (i = 0; i < keys.length; i++) {
            html += "<th>" + labels[keys[i]] + "</th>";
        }
        html += "</tr></thead><tbody>";
        for (i = 0; i < model.length; i++) {
            html += "<tr><th>" + escapeText(model[i].name || "") + "</th>";
            for (j = 0; j < keys.length; j++) {
                html += "<td>" + formatStatNumber(model[i].stats[keys[j]]) + "</td>";
            }
            html += "</tr>";
        }
        html += "</tbody></table></div>";
        return html;
    }

    function statsAoa(meta) {
        var model = seriesStatsModel(meta);
        if (!model.length) {
            return [];
        }
        var head = [
            "",
            _t("n"),
            _t("Min"),
            _t("Max"),
            _t("Mean"),
            _t("Median"),
            _t("Std. dev."),
            _t("Sum"),
        ];
        var keys = ["n", "min", "max", "mean", "median", "stdev", "sum"];
        var rows = [head];
        var i;
        var j;
        for (i = 0; i < model.length; i++) {
            var row = [model[i].name || ""];
            for (j = 0; j < keys.length; j++) {
                row.push(formatStatNumber(model[i].stats[keys[j]]));
            }
            rows.push(row);
        }
        return rows;
    }

    function maybeMountSeriesStats(block, rows, chartMeta) {
        if (!showSeriesStats) {
            return;
        }
        var statsMeta = analyzeForStats(rows) || chartMeta;
        if (!statsMeta) {
            return;
        }
        mountSeriesStats(block, statsMeta);
    }

    function mountSeriesStats(block, meta) {
        if (!block || !block.querySelector) {
            return;
        }
        var existing = block.querySelector(".o_chatboo_series_stats");
        if (existing && existing.parentNode) {
            existing.parentNode.removeChild(existing);
        }
        var html = statsTableHtml(meta);
        if (!html) {
            return;
        }
        var wrap = document.createElement("div");
        wrap.innerHTML = html;
        var node = wrap.firstChild;
        var host = block.querySelector(".o_ai_chart_host");
        if (host && host.parentNode) {
            if (host.nextSibling) {
                host.parentNode.insertBefore(node, host.nextSibling);
            } else {
                host.parentNode.appendChild(node);
            }
            return;
        }
        block.appendChild(node);
    }

    function parseSortNumber(raw) {
        var t = String(raw || "").trim();
        if (!t) {
            return null;
        }
        if (/^-?\d+(\.\d+)?$/.test(t)) {
            return parseFloat(t);
        }
        var compact = t.replace(/\s/g, "");
        if (/^-?[\d.]+,\d+$/.test(compact)) {
            return parseFloat(compact.replace(/\./g, "").replace(",", "."));
        }
        return null;
    }

    function cellSortKey(td) {
        if (!td) {
            return { n: null, s: "" };
        }
        var raw = td.getAttribute("data-ai-sort");
        if (raw == null || raw === "") {
            raw = (td.textContent || "").trim();
        }
        return { n: parseSortNumber(raw), s: String(raw).toLowerCase() };
    }

    function compareSortKeys(a, b, dir) {
        var sign = dir === "desc" ? -1 : 1;
        if (a.n != null && b.n != null && !isNaN(a.n) && !isNaN(b.n)) {
            if (a.n < b.n) {
                return -1 * sign;
            }
            if (a.n > b.n) {
                return 1 * sign;
            }
            return 0;
        }
        if (a.s < b.s) {
            return -1 * sign;
        }
        if (a.s > b.s) {
            return 1 * sign;
        }
        return 0;
    }

    function refreshOpenChart(table) {
        var block = table && table.closest && table.closest(".o_ai_table_block");
        if (
            block &&
            block.getAttribute("data-chatboo-chart-open") === "1" &&
            block._chatbooChartMeta
        ) {
            renderChart(
                block,
                block._chatbooChartMeta,
                block._chatbooChartMode || block._chatbooChartMeta.defaultMode
            );
        }
    }

    function applyTableSort(table, col, dir, secondary) {
        var tbody = table.tBodies && table.tBodies[0];
        if (!tbody) {
            return;
        }
        var rows = Array.prototype.slice.call(tbody.rows || []);
        rows.forEach(function (tr, i) {
            if (tr.getAttribute("data-chatboo-ord") == null) {
                tr.setAttribute("data-chatboo-ord", String(i));
            }
        });
        if (dir === "none" || col < 0) {
            rows.sort(function (a, b) {
                return (
                    Number(a.getAttribute("data-chatboo-ord") || 0) -
                    Number(b.getAttribute("data-chatboo-ord") || 0)
                );
            });
        } else {
            rows.sort(function (a, b) {
                var primary = compareSortKeys(
                    cellSortKey(a.cells[col]),
                    cellSortKey(b.cells[col]),
                    dir
                );
                if (primary !== 0) {
                    return primary;
                }
                if (
                    secondary
                    && secondary.dir
                    && secondary.dir !== "none"
                    && secondary.col >= 0
                ) {
                    var sec = compareSortKeys(
                        cellSortKey(a.cells[secondary.col]),
                        cellSortKey(b.cells[secondary.col]),
                        secondary.dir
                    );
                    if (sec !== 0) {
                        return sec;
                    }
                }
                return (
                    Number(a.getAttribute("data-chatboo-ord") || 0) -
                    Number(b.getAttribute("data-chatboo-ord") || 0)
                );
            });
        }
        rows.forEach(function (tr) {
            tbody.appendChild(tr);
        });
        var heads = table.querySelectorAll("thead th.o_ai_th_sort");
        var i;
        for (i = 0; i < heads.length; i++) {
            var th = heads[i];
            var idx = Number(th.getAttribute("data-ai-sort-col"));
            if (idx === col && dir !== "none") {
                th.setAttribute(
                    "aria-sort",
                    dir === "desc" ? "descending" : "ascending"
                );
            } else {
                th.setAttribute("aria-sort", "none");
            }
        }
        refreshOpenChart(table);
    }

    function cycleSortOnHeader(table, th) {
        var col = Number(th.getAttribute("data-ai-sort-col"));
        if (isNaN(col)) {
            return;
        }
        var state = table._chatbooSort || { col: -1, dir: "none", secondary: null };
        if (state.col === col) {
            state.dir =
                state.dir === "asc"
                    ? "desc"
                    : state.dir === "desc"
                      ? "none"
                      : "asc";
            if (state.dir === "none") {
                state.secondary = null;
                state.col = -1;
            }
        } else {
            if (state.dir !== "none" && state.col >= 0) {
                state.secondary = { col: state.col, dir: state.dir };
            } else {
                state.secondary = null;
            }
            state.col = col;
            state.dir = "asc";
        }
        table._chatbooSort = state;
        applyTableSort(table, state.col, state.dir, state.secondary);
    }

    var COL_DRAG_THRESHOLD = 6;

    function tableSectionRows(table) {
        var rows = [];
        var collect = function (section) {
            if (!section) {
                return;
            }
            var r;
            for (r = 0; r < section.rows.length; r++) {
                var tr = section.rows[r];
                if (tr.classList && tr.classList.contains("o_ai_ficha_title")) {
                    continue;
                }
                rows.push(tr);
            }
        };
        collect(table.tHead);
        var b;
        for (b = 0; b < (table.tBodies || []).length; b++) {
            collect(table.tBodies[b]);
        }
        collect(table.tFoot);
        return rows;
    }

    function moveTableColumn(table, fromIdx, toIdx) {
        if (fromIdx === toIdx || fromIdx < 0 || toIdx < 0) {
            return;
        }
        var rows = tableSectionRows(table);
        var r;
        for (r = 0; r < rows.length; r++) {
            var cells = rows[r].cells;
            if (!cells || fromIdx >= cells.length || toIdx >= cells.length) {
                continue;
            }
            var cell = cells[fromIdx];
            if (!cell) {
                continue;
            }
            if (fromIdx < toIdx) {
                var ref = cells[toIdx];
                if (ref && ref.nextSibling) {
                    rows[r].insertBefore(cell, ref.nextSibling);
                } else {
                    rows[r].appendChild(cell);
                }
            } else {
                rows[r].insertBefore(cell, cells[toIdx]);
            }
        }
    }

    function reindexSortCols(table) {
        var ths = table.querySelectorAll("thead th.o_ai_th_sort");
        var map = {};
        var i;
        for (i = 0; i < ths.length; i++) {
            var old = Number(ths[i].getAttribute("data-ai-sort-col"));
            if (!isNaN(old)) {
                map[old] = i;
            }
            ths[i].setAttribute("data-ai-sort-col", String(i));
        }
        var state = table._chatbooSort;
        if (!state) {
            return;
        }
        if (state.col >= 0 && map[state.col] != null) {
            state.col = map[state.col];
        }
        if (state.secondary && state.secondary.col >= 0 && map[state.secondary.col] != null) {
            state.secondary.col = map[state.secondary.col];
        }
    }

    function titleCaseKey(key) {
        return String(key || "").replace(/_/g, " ").replace(/\S+/g, function (word) {
            return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
        });
    }

    function matchDatasetKey(label, keys, used) {
        var want = String(label || "").replace(/\s+/g, " ").trim();
        var k;
        for (k = 0; k < keys.length; k++) {
            if (used[keys[k]]) {
                continue;
            }
            var titled = titleCaseKey(keys[k]).replace(/\s+/g, " ").trim();
            if (keys[k] === want || titled === want) {
                return keys[k];
            }
        }
        return "";
    }

    function rewriteDatasetColumnOrder(table) {
        var block = table.closest && table.closest(".o_ai_table_block");
        if (!block) {
            return;
        }
        var raw = block.getAttribute("data-ai-dataset");
        if (!raw) {
            return;
        }
        var rows;
        try {
            rows = JSON.parse(raw);
        } catch (eParse) {
            return;
        }
        if (!Array.isArray(rows) || !rows.length) {
            return;
        }
        var keys = columnKeys(rows);
        var ths = table.querySelectorAll("thead th.o_ai_th_sort");
        var ordered = [];
        var used = {};
        var i;
        var k;
        for (i = 0; i < ths.length; i++) {
            var hit = matchDatasetKey(headerCellLabel(ths[i]), keys, used);
            if (hit) {
                ordered.push(hit);
                used[hit] = 1;
            }
        }
        for (k = 0; k < keys.length; k++) {
            if (!used[keys[k]]) {
                ordered.push(keys[k]);
            }
        }
        if (!ordered.length) {
            return;
        }
        var next = rows.map(function (row) {
            if (!row || typeof row !== "object") {
                return row;
            }
            var out = {};
            var j;
            for (j = 0; j < ordered.length; j++) {
                if (Object.prototype.hasOwnProperty.call(row, ordered[j])) {
                    out[ordered[j]] = row[ordered[j]];
                }
            }
            Object.keys(row).forEach(function (key) {
                if (!Object.prototype.hasOwnProperty.call(out, key)) {
                    out[key] = row[key];
                }
            });
            return out;
        });
        block.setAttribute("data-ai-dataset", JSON.stringify(next));
        var meta = block._chatbooChartMeta;
        if (meta && meta.seriesKeys && meta.seriesKeys.length) {
            var keep = {};
            meta.seriesKeys.forEach(function (key) {
                keep[key] = 1;
            });
            var series = [];
            ordered.forEach(function (key) {
                if (keep[key]) {
                    series.push(key);
                }
            });
            meta.seriesKeys.forEach(function (key) {
                if (series.indexOf(key) < 0) {
                    series.push(key);
                }
            });
            meta.seriesKeys = series;
        }
    }

    function colReorderHost(table) {
        return (
            (table.closest && table.closest(".table-responsive"))
            || table.parentNode
            || table
        );
    }

    function hideColGuide(table) {
        var host = colReorderHost(table);
        if (!host) {
            return;
        }
        var guide = host._chatbooColGuide;
        if (guide && guide.parentNode) {
            guide.parentNode.removeChild(guide);
        }
        host._chatbooColGuide = null;
    }

    function dropIndexFromClientX(table, clientX) {
        var ths = table.querySelectorAll("thead th.o_ai_th_sort");
        var i;
        for (i = 0; i < ths.length; i++) {
            var box = ths[i].getBoundingClientRect();
            if (clientX < box.left + box.width / 2) {
                return i;
            }
        }
        return ths.length ? ths.length - 1 : 0;
    }

    function showColGuide(table, toIdx, fromIdx) {
        var ths = table.querySelectorAll("thead th.o_ai_th_sort");
        var th = ths[toIdx];
        var host = colReorderHost(table);
        if (!th || !host || !host.appendChild) {
            return;
        }
        var guide = host._chatbooColGuide;
        if (!guide) {
            guide = global.document.createElement("div");
            guide.className = "o_chatboo_col_reorder_guide";
            guide.setAttribute("aria-hidden", "true");
            host.appendChild(guide);
            host._chatbooColGuide = guide;
        }
        var hostRect = host.getBoundingClientRect();
        var thRect = th.getBoundingClientRect();
        var tableRect = table.getBoundingClientRect();
        var x = fromIdx < toIdx
            ? thRect.right - hostRect.left + (host.scrollLeft || 0)
            : thRect.left - hostRect.left + (host.scrollLeft || 0);
        guide.style.left = x + "px";
        guide.style.top = (tableRect.top - hostRect.top + (host.scrollTop || 0)) + "px";
        guide.style.height = tableRect.height + "px";
    }

    function bindHeaderPointer(table, th) {
        th.addEventListener("pointerdown", function (ev) {
            if (ev.button != null && ev.button !== 0) {
                return;
            }
            if (ev.target && ev.target.closest && ev.target.closest("a")) {
                return;
            }
            var fromIdx = Number(th.getAttribute("data-ai-sort-col"));
            var startX = ev.clientX;
            var startY = ev.clientY;
            var dragged = false;
            var lastTo = fromIdx;
            var colCount = table.querySelectorAll("thead th.o_ai_th_sort").length;
            var onMove = function (e) {
                if (
                    !dragged
                    && Math.abs(e.clientX - startX) < COL_DRAG_THRESHOLD
                    && Math.abs(e.clientY - startY) < COL_DRAG_THRESHOLD
                ) {
                    return;
                }
                if (colCount < 2 || isNaN(fromIdx)) {
                    return;
                }
                dragged = true;
                table.classList.add("o_chatboo_col_reordering");
                th.classList.add("is-dragging");
                lastTo = dropIndexFromClientX(table, e.clientX);
                showColGuide(table, lastTo, fromIdx);
            };
            var onUp = function () {
                document.removeEventListener("pointermove", onMove);
                document.removeEventListener("pointerup", onUp);
                document.removeEventListener("pointercancel", onUp);
                hideColGuide(table);
                th.classList.remove("is-dragging");
                table.classList.remove("o_chatboo_col_reordering");
                if (dragged) {
                    if (lastTo !== fromIdx && !isNaN(fromIdx)) {
                        moveTableColumn(table, fromIdx, lastTo);
                        reindexSortCols(table);
                        rewriteDatasetColumnOrder(table);
                        refreshOpenChart(table);
                    }
                } else {
                    cycleSortOnHeader(table, th);
                }
            };
            document.addEventListener("pointermove", onMove);
            document.addEventListener("pointerup", onUp);
            document.addEventListener("pointercancel", onUp);
            ev.preventDefault();
        });
    }

    function bindSortableTables(root) {
        if (!root || !root.querySelectorAll) {
            return;
        }
        var tables = root.querySelectorAll("table.o_ai_data_table");
        var t;
        for (t = 0; t < tables.length; t++) {
            var table = tables[t];
            if (table.getAttribute("data-chatboo-sort-bound") === "1") {
                continue;
            }
            var ths = table.querySelectorAll("thead th.o_ai_th_sort");
            if (!ths.length) {
                var plain = table.querySelectorAll(
                    "thead tr:last-child th"
                );
                var p;
                for (p = 0; p < plain.length; p++) {
                    if (plain[p].closest("tr.o_ai_ficha_title")) {
                        continue;
                    }
                    plain[p].classList.add("o_ai_th_sort");
                    plain[p].setAttribute("data-ai-sort-col", String(p));
                    plain[p].setAttribute("aria-sort", "none");
                }
                ths = table.querySelectorAll("thead th.o_ai_th_sort");
            }
            if (!ths.length) {
                continue;
            }
            table.setAttribute("data-chatboo-sort-bound", "1");
            table._chatbooSort = { col: -1, dir: "none", secondary: null };
            Array.prototype.forEach.call(ths, function (th) {
                bindHeaderPointer(table, th);
            });
        }
    }

    // ── Canvas: every table of one answer laid out as a page ──
    // The chat client sets the host only when a provider has the Design
    // tick. ``rpc(route, params)`` returns a promise; ``sessionId()`` and
    // ``question(msgIndex)`` read the client state.
    var CANVAS_POLL_MS = 3000;
    var CANVAS_WAIT_MS = 7 * 60 * 1000;
    var canvasHost = null;
    var canvasJobs = {};

    function setCanvas(host) {
        canvasHost = host && typeof host.rpc === "function" ? host : null;
        if (typeof document !== "undefined") {
            mountCanvasButtons(document);
        }
    }

    function messageRowOf(block) {
        return block && block.closest ? block.closest("[data-msg-index]") : null;
    }

    function canvasJobKey(row) {
        var sid = canvasHost && canvasHost.sessionId ? canvasHost.sessionId() : "";
        return String(sid || "") + ":" + row.getAttribute("data-msg-index");
    }

    function canvasTablesOf(row) {
        var out = [];
        var blocks = row.querySelectorAll(".o_ai_table_block[data-ai-dataset]");
        for (var i = 0; i < blocks.length; i++) {
            var rows;
            try {
                rows = JSON.parse(blocks[i].getAttribute("data-ai-dataset") || "[]");
            } catch (e) {
                continue;
            }
            if (!Array.isArray(rows) || !rows.length) {
                continue;
            }
            var head = blocks[i].querySelector(
                ".o_ai_block_title, .o_ai_ficha_title, .pns-result-title"
            );
            out.push({
                title: head ? (head.textContent || "").replace(/\s+/g, " ").trim() : "",
                rows: rows,
            });
        }
        return out;
    }

    /** The answer's own heading, above its tables. */
    function canvasTitleOf(row) {
        var head = row.querySelector(".o_ai_result_title, .o_ai_dashboard_title");
        return head ? (head.textContent || "").replace(/\s+/g, " ").trim() : "";
    }

    /** Every table of the answer shows the same page, so they share its state. */
    function paintCanvasRow(row, job) {
        var buttons = row && row.querySelectorAll
            ? row.querySelectorAll(".o_chatboo_canvas_btn")
            : [];
        for (var i = 0; i < buttons.length; i++) {
            paintCanvasButton(buttons[i], job);
        }
    }

    function paintCanvasButton(btn, job) {
        if (!btn) {
            return;
        }
        var state = job ? job.state : "";
        btn.classList.toggle("o_chatboo_canvas_btn--failed", state === "failed");
        btn.classList.toggle("o_chatboo_canvas_btn--building", state === "building");
        if (state === "building") {
            var dots = document.createElement("span");
            dots.className = "o_chatboo_typing";
            for (var d = 0; d < 3; d++) {
                dots.appendChild(document.createElement("span"));
            }
            btn.textContent = "";
            btn.appendChild(dots);
            btn.appendChild(document.createTextNode(" " + label("canvasBuilding")));
            btn.setAttribute("title", label("canvasCancel"));
        } else if (state === "done") {
            btn.textContent = label("canvasOpen");
            btn.setAttribute("title", job.url);
        } else if (state === "failed") {
            btn.textContent = label("canvas");
            btn.setAttribute("title", job.error || label("canvasFailed"));
        } else {
            btn.textContent = label("canvas");
            btn.setAttribute("title", label("canvasTitle"));
        }
    }

    function waitForCanvas(jobId) {
        var deadline = Date.now() + CANVAS_WAIT_MS;
        return new Promise(function (resolve, reject) {
            function tick() {
                Promise.resolve(
                    canvasHost.rpc("/chatboo/canvas/state", { job_id: jobId })
                ).then(function (st) {
                    if (!st || st.status !== "ok") {
                        reject(new Error((st && st.message) || ""));
                        return;
                    }
                    if (st.state === "done") {
                        resolve(st.url);
                        return;
                    }
                    if (st.state !== "building") {
                        reject(new Error(st.error || ""));
                        return;
                    }
                    if (Date.now() > deadline) {
                        reject(new Error(""));
                        return;
                    }
                    global.setTimeout(tick, CANVAS_POLL_MS);
                }, reject);
            }
            global.setTimeout(tick, CANVAS_POLL_MS);
        });
    }

    function followCanvas(job) {
        waitForCanvas(job.jobId).then(function (url) {
            if (job.cancelled) {
                return;
            }
            job.state = "done";
            job.url = url;
            paintCanvasRow(job.row, job);
        }, function (err) {
            if (job.cancelled) {
                return;
            }
            job.state = "failed";
            job.error = (err && err.message) || "";
            paintCanvasRow(job.row, job);
        });
    }

    function startCanvas(row) {
        if (!canvasHost) {
            return;
        }
        var key = canvasJobKey(row);
        var job = canvasJobs[key];
        if (job && job.state === "done") {
            global.open(job.url, "_blank", "noopener");
            return;
        }
        if (job && job.state === "building") {
            cancelCanvas(key, job);
            return;
        }
        var sessionId = canvasHost.sessionId ? canvasHost.sessionId() : null;
        var tables = canvasTablesOf(row);
        if (!sessionId || !tables.length) {
            return;
        }
        var msgIndex = parseInt(row.getAttribute("data-msg-index"), 10);
        job = canvasJobs[key] = { state: "building", row: row };
        paintCanvasRow(row, job);
        Promise.resolve(canvasHost.rpc("/chatboo/canvas/build", {
            session_id: sessionId,
            tables: tables,
            title: canvasTitleOf(row),
            question: canvasHost.question ? (canvasHost.question(msgIndex) || "") : "",
            msg_index: msgIndex,
        })).then(function (res) {
            if (!res || res.status !== "ok") {
                throw new Error((res && res.message) || "");
            }
            job.jobId = res.job_id;
            if (job.cancelled) {
                cancelCanvasJob(job.jobId);
                return;
            }
            if (res.state === "done") {
                job.state = "done";
                job.url = res.url;
                paintCanvasRow(job.row, job);
            } else if (res.state === "building") {
                followCanvas(job);
            } else {
                throw new Error(res.error || "");
            }
        }).catch(function (err) {
            if (job.cancelled) {
                return;
            }
            job.state = "failed";
            job.error = (err && err.message) || "";
            paintCanvasRow(job.row, job);
        });
    }

    /** A click while building asks first, like the chat; yes drops the page on the server. */
    function cancelCanvas(key, job) {
        if (!canvasHost.confirmCancel) {
            return;
        }
        canvasHost.confirmCancel(function () {
            if (canvasJobs[key] === job && job.state === "building") {
                dropCanvas(key, job);
            }
        });
    }

    function dropCanvas(key, job) {
        job.cancelled = true;
        if (canvasJobs[key] === job) {
            delete canvasJobs[key];
        }
        paintCanvasRow(job.row, null);
        if (job.jobId) {
            cancelCanvasJob(job.jobId);
        }
    }

    function cancelCanvasJob(jobId) {
        Promise.resolve(canvasHost.rpc("/chatboo/canvas/cancel", {
            job_id: jobId,
        })).catch(function () {});
    }

    /** After a reload, the pages still on their way show their dots again. */
    var canvasResumed = {};

    function resumeCanvas() {
        var sessionId = canvasHost && canvasHost.sessionId ? canvasHost.sessionId() : null;
        if (!sessionId || canvasResumed[sessionId]) {
            return;
        }
        canvasResumed[sessionId] = true;
        Promise.resolve(canvasHost.rpc("/chatboo/canvas/running", {
            session_id: sessionId,
        })).then(function (res) {
            var jobs = (res && res.status === "ok" && res.jobs) || [];
            jobs.forEach(function (st) {
                var key = String(sessionId) + ":" + st.msg_index;
                if (st.state !== "building" || canvasJobs[key]) {
                    return;
                }
                var row = document.querySelector('[data-msg-index="' + st.msg_index + '"]');
                var job = canvasJobs[key] = {
                    state: "building",
                    jobId: st.job_id,
                    row: row,
                };
                paintCanvasRow(row, job);
                followCanvas(job);
            });
        }).catch(function () {
            delete canvasResumed[sessionId];
        });
    }

    function dropCanvasButton(btn) {
        var bar = btn.parentNode;
        btn.remove();
        if (bar && bar.classList.contains("o_chatboo_canvas_bar") && !bar.children.length) {
            bar.remove();
        }
    }

    function ownToolbar(block) {
        for (var i = 0; i < block.children.length; i++) {
            if (block.children[i].classList.contains("o_ai_chart_toolbar")) {
                return block.children[i];
            }
        }
        return null;
    }

    function canvasButtonIn(block) {
        var bar = ownToolbar(block);
        return bar ? bar.querySelector(".o_chatboo_canvas_btn") : null;
    }

    /** One page per answer, from every table. Each table carries the button. */
    function mountCanvasButton(block) {
        var row = messageRowOf(block);
        if (!row) {
            return;
        }
        var own = canvasButtonIn(block);
        if (!canvasHost) {
            if (own) {
                dropCanvasButton(own);
            }
            return;
        }
        if (!canvasTablesOf(row).length) {
            if (own) {
                dropCanvasButton(own);
            }
            return;
        }
        if (own) {
            return;
        }
        var bar = ownToolbar(block);
        if (!bar) {
            bar = document.createElement("div");
            bar.className = "o_ai_chart_toolbar o_chatboo_canvas_bar o_ai_noexport";
            block.appendChild(bar);
        }
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-sm o_chatboo_canvas_btn";
        bar.insertBefore(btn, bar.firstChild);
        var job = canvasJobs[canvasJobKey(row)];
        if (job) {
            job.row = row;
        }
        paintCanvasButton(btn, job);
        btn.addEventListener("click", function () {
            startCanvas(row);
        });
    }

    function mountCanvasButtons(root) {
        if (!root || !root.querySelectorAll) {
            return;
        }
        if (canvasHost) {
            resumeCanvas();
        }
        var blocks = root.querySelectorAll(".o_ai_table_block[data-ai-dataset]");
        for (var i = 0; i < blocks.length; i++) {
            mountCanvasButton(blocks[i]);
        }
    }

    function hydrateRoot(root) {
        if (!root || !root.querySelectorAll) {
            return;
        }
        bindSortableTables(root);
        var blocks = root.querySelectorAll(".o_ai_table_block[data-ai-dataset]");
        for (var i = 0; i < blocks.length; i++) {
            var block = blocks[i];
            if (block.getAttribute("data-chatboo-chart-ready") === "1") {
                continue;
            }
            if (!chartsAllowedForBlock(block)) {
                block.setAttribute("data-chatboo-chart-ready", "1");
                continue;
            }
            var raw = block.getAttribute("data-ai-dataset");
            if (!raw) {
                continue;
            }
            var rows;
            try {
                rows = JSON.parse(raw);
            } catch (e) {
                continue;
            }
            if (!Array.isArray(rows) || !rows.length) {
                continue;
            }
            rows = rowsForChart(rows);
            if (!rows.length) {
                continue;
            }
            var explicitChart = isChartTableMode(block);
            var analyzeOpts = explicitChart ? {} : { metricsOnly: true };
            var meta = analyzeDataset(rows, analyzeOpts);
            if (!meta) {
                var pivoted = tryPivotLongRows(rows);
                if (pivoted) {
                    meta = analyzeDataset(pivoted, analyzeOpts);
                    if (meta) {
                        rows = pivoted;
                    }
                }
            }
            if (!meta) {
                maybeMountSeriesStats(block, rows, null);
                block.setAttribute("data-chatboo-chart-ready", "1");
                continue;
            }
            if (isKpiLabelValueMeta(meta)) {
                maybeMountSeriesStats(block, rows, meta);
                block.setAttribute("data-chatboo-chart-ready", "1");
                continue;
            }
            if (!shouldOfferChart(block, meta, rows)) {
                maybeMountSeriesStats(block, rows, meta);
                block.setAttribute("data-chatboo-chart-ready", "1");
                continue;
            }
            applyDualAxisOverride(meta, block);
            mountToolbarOrFallback(block, meta);
            block.setAttribute("data-chatboo-chart-ready", "1");
        }
        mountCanvasButtons(root);
    }

    function destroyInRoot(root) {
        if (!root || !root.querySelectorAll) {
            return;
        }
        var blocks = root.querySelectorAll(".o_ai_table_block");
        for (var i = 0; i < blocks.length; i++) {
            destroyChart(blocks[i]);
        }
    }

    function largestCanvas(root) {
        var canvases = root && root.querySelectorAll ? root.querySelectorAll("canvas") : [];
        var best = null;
        var area = 0;
        var i;
        for (i = 0; i < canvases.length; i++) {
            var canvas = canvases[i];
            var next = (canvas.width || 0) * (canvas.height || 0);
            if (next > area) {
                area = next;
                best = canvas;
            }
        }
        return best;
    }

    function chartInstancePng(inst) {
        if (!inst) {
            return "";
        }
        try {
            if (typeof inst.getDataURL === "function") {
                return inst.getDataURL({
                    type: "png",
                    pixelRatio: 2,
                    backgroundColor: "#ffffff",
                }) || "";
            }
        } catch (e) { /* */ }
        try {
            if (typeof inst.toBase64Image === "function") {
                return inst.toBase64Image("image/png", 1) || "";
            }
        } catch (e2) { /* */ }
        return "";
    }

    function resolveChartInstance(block) {
        if (block && block._chatbooChart) {
            return block._chatbooChart;
        }
        var surface =
            block &&
            block.querySelector &&
            block.querySelector(".o_ai_echarts_surface");
        if (
            surface &&
            EchartsLib &&
            typeof EchartsLib.getInstanceByDom === "function"
        ) {
            return EchartsLib.getInstanceByDom(surface);
        }
        return null;
    }

    function canvasToPng(canvas) {
        if (!canvas) {
            return "";
        }
        try {
            return canvas.toDataURL("image/png") || "";
        } catch (e) {
            return "";
        }
    }

    function metaFromDataset(block) {
        var raw =
            block &&
            block.getAttribute &&
            block.getAttribute("data-ai-dataset");
        if (!raw) {
            return null;
        }
        var rows;
        try {
            rows = JSON.parse(raw);
        } catch (e) {
            return null;
        }
        if (!Array.isArray(rows) || !rows.length) {
            return null;
        }
        rows = rowsForChart(rows);
        if (!rows.length) {
            return null;
        }
        var explicit = isChartTableMode(block);
        var opts = explicit ? {} : { metricsOnly: true };
        var meta = analyzeDataset(rows, opts);
        if (!meta) {
            var pivoted = tryPivotLongRows(rows);
            if (pivoted) {
                meta = analyzeDataset(pivoted, opts);
                if (meta) {
                    rows = pivoted;
                }
            }
        }
        if (!meta) {
            return null;
        }
        if (!explicit && !shouldOfferChart(block, meta, rows)) {
            return null;
        }
        return meta;
    }

    function snapshotBlockPng(block) {
        if (!block || !chartsAllowedForBlock(block)) {
            return "";
        }
        var png = chartInstancePng(resolveChartInstance(block));
        if (png) {
            return png;
        }
        var host = block.querySelector && block.querySelector(".o_ai_chart_host");
        png = canvasToPng(largestCanvas(host));
        if (png) {
            return png;
        }
        var meta = block._chatbooChartMeta || metaFromDataset(block);
        if (!meta) {
            return "";
        }
        var wasOpen = block.getAttribute("data-chatboo-chart-open") === "1";
        try {
            renderChart(block, meta, block._chatbooChartMode || meta.defaultMode);
            png = chartInstancePng(resolveChartInstance(block));
            if (!png) {
                png = canvasToPng(largestCanvas(
                    block.querySelector && block.querySelector(".o_ai_chart_host")
                ));
            }
        } catch (e) {
            png = "";
        }
        if (!wasOpen) {
            hideChart(block);
            block._chatbooChartMeta = meta;
        }
        return png || "";
    }

    function analyzeForStats(rows) {
        if (!Array.isArray(rows) || !rows.length) {
            return null;
        }
        var meta = analyzeDataset(rows, {});
        if (!meta) {
            var pivoted = tryPivotLongRows(rows);
            if (pivoted) {
                meta = analyzeDataset(pivoted, {});
            }
        }
        return meta || null;
    }

    global.ChatbooCharts = {
        bindEngines: bindEngines,
        hydrate: hydrateRoot,
        destroyIn: destroyInRoot,
        analyze: analyzeDataset,
        analyzeForStats: analyzeForStats,
        needsDualAxis: needsDualAxis,
        isRatioLikeKey: isRatioLikeKey,
        isMoneyLikeKey: isMoneyLikeKey,
        isCountLikeKey: isCountLikeKey,
        isChartMetricKey: isChartMetricKey,
        categoryAxisIsTemporal: categoryAxisIsTemporal,
        shouldOfferChart: shouldOfferChart,
        setLabels: setLabels,
        setCanvas: setCanvas,
        resolveHostHeight: resolveChartHostHeightPx,
        relayout: relayoutChartsIn,
        softResize: softResizeChartsIn,
        snapshotPng: snapshotBlockPng,
        statsTableHtml: statsTableHtml,
        statsAoa: statsAoa,
        seriesStatsModel: seriesStatsModel,
        mountSeriesStats: mountSeriesStats,
        setShowSeriesStats: setShowSeriesStats,
        getShowSeriesStats: getShowSeriesStats,
    };

    // Copiar texto de celda (coords, etc.): data-copy-text en .o_ai_cell_copy
    function bindCellCopyOnce() {
        if (global.__chatbooCellCopyBound) {
            return;
        }
        global.__chatbooCellCopyBound = true;
        document.addEventListener(
            "click",
            function (ev) {
                var el = ev.target;
                if (!el || !el.closest) {
                    return;
                }
                var btn = el.closest(".o_ai_cell_copy");
                if (!btn) {
                    return;
                }
                if (!btn.closest(".o_chatboo_content, .o_chatboo_floating, .o_chatboo_app, .o_chatboo_message")) {
                    return;
                }
                ev.preventDefault();
                ev.stopPropagation();
                var text = btn.getAttribute("data-copy-text") || "";
                if (!text) {
                    return;
                }
                var icon = btn.querySelector("i") || btn;
                var originalClass = icon.className;
                var flash = function () {
                    icon.className = "fa fa-check text-success";
                    setTimeout(function () {
                        icon.className = originalClass;
                    }, 1500);
                };
                var fallback = function () {
                    var ta = document.createElement("textarea");
                    ta.value = text;
                    ta.setAttribute("readonly", "");
                    ta.style.position = "fixed";
                    ta.style.left = "-9999px";
                    document.body.appendChild(ta);
                    ta.select();
                    try {
                        document.execCommand("copy");
                        flash();
                    } catch (e) {
                        /* ignore */
                    }
                    document.body.removeChild(ta);
                };
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(flash).catch(fallback);
                } else {
                    fallback();
                }
            },
            true
        );
    }
    bindCellCopyOnce();
})(typeof window !== "undefined" ? window : this);

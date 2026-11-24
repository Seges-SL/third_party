# Copyright 2026 Seges
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
"""sanitizeHtml of pns_ai_chatboo, run in the lab browser (stage F1.5, decision 100).

The sanitizer is the module's own: chatboo_formatters.js is an @odoo-module in
web.assets_backend, so the page /web exposes it as
odoo.loader.modules.get("@pns_ai_chatboo/js/chatboo_formatters").sanitizeHtml.
Each test opens /web as admin (like pns_base TestWebClientStarts), waits for
that module and runs the checks in the page. Inputs are synthetic and minimal:
they test one rule each and carry no payload.

- test_t1_rules_hold (T1): on* attributes go; javascript: links go, also in
  <svg><a>; an external <img> goes through /pns_ai_mcp/remote_image; an
  external url() in style goes; <math> and <template> go.
- test_t2a_idempotent_and_live (T2a): sanitizing the output again changes
  nothing, and once inserted in a live node there is no on* attribute and no
  href outside http, https, mailto, tel or a same-origin blob. The external
  <img> of T1 is left out of this corpus: in a live node it would fetch
  /pns_ai_mcp/remote_image, and that request is not what T2a checks.
- test_t2b_no_chat_controls (T2b): the output carries none of the elements
  the chat client takes as its own controls ([id^="pns_verif_"],
  [id^="pns_choice_"], .o_ai_svg_card[data-ai-card], .o_ai_cell_copy,
  a.o_ai_namelink). Red today (F1-9, F1-10, F1-11).

Idempotence and the cache: sanitizeHtml keeps a cache that maps its output to
itself, so sanitizeHtml(out) would come from the cache. T2a sanitizes
out + "<!---->" instead: a new key, so a real pass, and the sanitizer drops
comments, so the expected result is exactly out.

Every failure message starts with a tag:
- [CHECK]: the behaviour this test documents did not hold;
- [HYPOTHESIS]: the check this test exists for failed (expected today);
- [SETUP]: a precondition failed; says nothing about the sanitizer.
"""

from odoo.tests import HttpCase, tagged

MODULE = "@pns_ai_chatboo/js/chatboo_formatters"

# Waits for the module, then runs BODY(sanitize, report) where report(tag,
# problems) ends the test. BODY is plain JS that returns nothing.
_FRAME = """
(function wait(left) {
    var mods = window.odoo && odoo.loader && odoo.loader.modules;
    var mod = mods && mods.get("%(module)s");
    if (!mod) {
        if (left <= 0) {
            console.error("[SETUP] module %(module)s not loaded in /web");
            return;
        }
        setTimeout(function () { wait(left - 1); }, 250);
        return;
    }
    if (typeof mod.sanitizeHtml !== "function") {
        console.error("[SETUP] %(module)s has no sanitizeHtml function");
        return;
    }
    if (mod.sanitizeHtml("<b>t</b>") !== "<b>t</b>") {
        console.error("[SETUP] sanitizeHtml does not keep a plain <b>: "
            + JSON.stringify(mod.sanitizeHtml("<b>t</b>")));
        return;
    }
    var sanitize = mod.sanitizeHtml;
    function inert(html) {
        var box = document.implementation.createHTMLDocument("").createElement("div");
        box.innerHTML = html;
        return box;
    }
    function report(tag, problems) {
        if (problems.length) {
            console.error(tag + " " + problems.join(" | "));
        } else {
            console.log("test successful");
        }
    }
    %(body)s
})(120);
"""

_T1 = r"""
var problems = [];
function rule(name, input, ok) {
    var out = sanitize(input);
    var verdict;
    try { verdict = ok(inert(out), out); } catch (e) { verdict = "threw " + e; }
    if (verdict !== true) {
        problems.push(name + ": " + JSON.stringify(input) + " -> " + JSON.stringify(out)
            + (verdict === false ? "" : " (" + verdict + ")"));
    }
    console.log("T1 " + name + ": " + (verdict === true ? "ok" : "FAIL") + " -> " + out);
}
function noOn(box) {
    return Array.prototype.every.call(box.querySelectorAll("*"), function (el) {
        return Array.prototype.every.call(el.attributes, function (a) {
            return a.name.toLowerCase().indexOf("on") !== 0;
        });
    });
}
rule("on_attribute", '<b onclick="x()">t</b>', function (box) {
    return noOn(box) && !!box.querySelector("b");
});
rule("javascript_href", '<a href="javascript:void(0)">t</a>', function (box) {
    var a = box.querySelector("a");
    return !a || !a.hasAttribute("href");
});
rule("javascript_href_in_svg", '<svg><a href="javascript:void(0)"><text>t</text></a></svg>', function (box) {
    return Array.prototype.every.call(box.querySelectorAll("a"), function (a) {
        return !a.hasAttribute("href") && !a.hasAttribute("xlink:href");
    });
});
rule("external_img", '<img src="https://example.invalid/a.png" alt="a">', function (box) {
    var img = box.querySelector("img");
    return !!img && (img.getAttribute("src") || "").indexOf("/pns_ai_mcp/remote_image?url=") === 0;
});
rule("external_css_url", '<span style="background:url(https://example.invalid/a.png)">t</span>', function (box, out) {
    return out.indexOf("example.invalid") < 0 && !!box.querySelector("span");
});
rule("math", "<math><mi>x</mi></math><p>t</p>", function (box) {
    return !box.querySelector("math") && !!box.querySelector("p");
});
rule("template", "<template><b>t</b></template><p>t</p>", function (box) {
    return !box.querySelector("template") && !!box.querySelector("p");
});
report("[CHECK]", problems);
"""

_T2A = r"""
var corpus = [
    '<b onclick="x()">t</b>',
    '<a href="javascript:void(0)">t</a>',
    '<svg><a href="javascript:void(0)"><text>t</text></a></svg>',
    '<span style="background:url(https://example.invalid/a.png)">t</span>',
    '<math><mi>x</mi></math><p>t</p>',
    '<template><b>t</b></template><p>t</p>',
    '<p>t<b>u</b></p><table><tr><td>1</td></tr></table>',
    '<svg viewBox="0 0 1 1"><title>t</title><rect width="1" height="1"/></svg>',
    '<custom-x onclick="x()">t</custom-x><a href="https://example.invalid/">t</a>',
    '<a href="mailto:a@example.invalid">t</a><a href="/web">t</a>',
];
var allowed = { "http:": 1, "https:": 1, "mailto:": 1, "tel:": 1 };
var problems = [];
var host = document.createElement("div");
host.style.display = "none";
document.body.appendChild(host);
corpus.forEach(function (input) {
    var out = sanitize(input);
    var again = sanitize(out + "<!---->");
    if (again !== out) {
        problems.push("not idempotent: " + JSON.stringify(input) + " -> "
            + JSON.stringify(out) + " -> " + JSON.stringify(again));
    }
    host.innerHTML = out;
    Array.prototype.forEach.call(host.querySelectorAll("*"), function (el) {
        Array.prototype.forEach.call(el.attributes, function (a) {
            var name = a.name.toLowerCase();
            if (name.indexOf("on") === 0) {
                problems.push("on* in live node: " + JSON.stringify(input) + " -> " + name);
            }
            if (name === "href" || name === "xlink:href") {
                var url;
                try { url = new URL(a.value, window.location.href); } catch (e) { url = null; }
                var ok = url && (allowed[url.protocol]
                    || (url.protocol === "blob:" && url.origin === window.location.origin));
                if (!ok) {
                    problems.push("href outside the list: " + JSON.stringify(input)
                        + " -> " + JSON.stringify(a.value));
                }
            }
        });
    });
    host.innerHTML = "";
});
host.remove();
console.log("T2a corpus size: " + corpus.length);
report("[CHECK]", problems);
"""

_T2B = r"""
var cases = [
    ['[id^="pns_verif_"]', '<div id="pns_verif_X0001">t</div>'],
    ['[id^="pns_choice_"]', '<div id="pns_choice_1">t</div>'],
    ['.o_ai_svg_card[data-ai-card]', '<div class="o_ai_svg_card" data-ai-card="{}">t</div>'],
    ['.o_ai_cell_copy', '<button class="o_ai_cell_copy" data-copy-text="t">c</button>'],
    ['a.o_ai_namelink', '<a class="o_ai_namelink" href="/web#id=1&amp;model=res.partner">t</a>'],
];
var kept = [];
cases.forEach(function (c) {
    var out = sanitize(c[1]);
    if (inert(out).querySelector(c[0])) {
        kept.push(c[0] + " kept: " + JSON.stringify(out));
    }
});
report("[HYPOTHESIS] chat controls in the output:", kept);
"""


@tagged("post_install", "-at_install")
class TestSanitizer17(HttpCase):

    def _run(self, body):
        code = _FRAME % {"module": MODULE, "body": body}
        self.browser_js("/web", code, login="admin", timeout=90)

    def test_t1_rules_hold(self):
        self._run(_T1)

    def test_t2a_idempotent_and_live(self):
        self._run(_T2A)

    def test_t2b_no_chat_controls(self):
        self._run(_T2B)

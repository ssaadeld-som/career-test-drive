"""Record a captioned demo video of the app (needs the server on :8000).

    python scripts/record_demo.py      # writes docs/demo.webm and docs/shots/demo_*.png
"""
import asyncio
import shutil
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8000/"
CAPTION_JS = """
(text) => {
  let el = document.getElementById('demo-cap');
  if (!el) {
    el = document.createElement('div'); el.id = 'demo-cap';
    el.style.cssText = 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:9999;max-width:86%;' +
      'background:rgba(11,31,58,.92);color:#fff;font:600 19px/1.4 Inter,system-ui,sans-serif;padding:12px 20px;' +
      'border-radius:14px;box-shadow:0 8px 24px rgba(0,0,0,.3);text-align:center;transition:opacity .3s';
    document.body.appendChild(el);
  }
  el.textContent = text; el.style.opacity = text ? 1 : 0;
}"""


async def cap(page, text, wait=2.8):
    await page.evaluate(CAPTION_JS, text)
    await page.wait_for_timeout(int(wait * 1000))


async def scroll_to(page, sel, offset=-120, wait=0.9):
    await page.evaluate("""([s,o]) => { const e=document.querySelector(s); window.scrollTo({top: e.getBoundingClientRect().top + window.scrollY + o, behavior: 'smooth'}); }""", [sel, offset])
    await page.wait_for_timeout(int(wait * 1000))


async def shot(page, name):
    await page.screenshot(path=ROOT / "docs" / "shots" / f"demo_{name}.png")


async def main():
    vids = ROOT / "docs" / "_video"
    shutil.rmtree(vids, ignore_errors=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(vids),
                                  record_video_size={"width": 1280, "height": 720})
        await ctx.add_init_script("try{if(!sessionStorage.getItem('demo')){localStorage.clear();sessionStorage.setItem('demo','1')}}catch(e){}")
        page = await ctx.new_page()

        # 1. Home + belief input
        await page.goto(URL); await page.wait_for_timeout(1200)
        await cap(page, "Career Test Drive: helps students aged 12–18 check what they believe about a career against real government data.", 4)
        await page.click("#career")
        await page.keyboard.type("lawyer", delay=90)
        await page.keyboard.press("Escape")
        await page.click("#beliefs")
        await page.keyboard.type("Lawyers argue in court every day and make $300k right out of school.", delay=28)
        await cap(page, "The student types a career and what they THINK it's like. Misconceptions are the input.", 3)
        await page.select_option("#state", "CT")
        await cap(page, "They pick their state (Connecticut) so pay and schools are local.", 2.5)
        await page.click("#go")
        await cap(page, "Five AI agents (gpt-6-luna) work in parallel: safety screen, career search, fact-check, test drive, road map.", 4)
        await shot(page, "crew")
        await page.wait_for_selector(".plain-card", timeout=90000)
        await page.wait_for_selector("#verdicts .vcard", timeout=90000)
        await page.wait_for_timeout(800)

        # 2. Overview + day in the life
        await scroll_to(page, "#overview", -130)
        await cap(page, "First, the job in plain words, with official pay, growth, openings and education.", 4)
        await shot(page, "overview")
        await scroll_to(page, "#day", -100)
        await cap(page, "A narrated 'day in the life', built from tasks real lawyers report (O*NET).", 2.5)
        await page.click("#pl-play")
        await page.wait_for_timeout(6500)
        await shot(page, "day")
        await page.click("#pl-next"); await page.wait_for_timeout(4000)
        await page.click("#pl-play")
        await scroll_to(page, "#specs", -160)
        await cap(page, "Different kinds of lawyer, explained simply: prosecutor, public defender, corporate…", 3.5)

        # 3. Myths vs facts
        await scroll_to(page, "#reality", -100)
        await cap(page, "Each belief gets a verdict with the exact government number behind it.", 3)
        await scroll_to(page, "#verdicts", -150)
        await cap(page, "'$300k right out of school' is a MYTH: entry-level pay is about $72,780 (BLS). Every number is checked against the data.", 5)
        await shot(page, "myths")

        # 4. Pay + state map
        await scroll_to(page, "#pay", -100)
        await cap(page, "Pay at three stages in Connecticut, plus what graduates of the usual majors earn 1 and 5 years out.", 4.5)
        await scroll_to(page, ".statewrap", -140)
        await cap(page, "Pay in every state, from BLS. Click any state to switch.", 3.5)

        # 5. Where to study
        await scroll_to(page, "#study", -100)
        await cap(page, "Where to study: majors that lead here, then schools that offer them (College Scorecard).", 4)
        await scroll_to(page, "#school-filters", -120)
        await cap(page, "Ranked by graduates' earnings, with graduation rate, admission rate and net price. Filter by state and program type.", 4.5)
        await shot(page, "schools")

        # 6. Field ecosystem + save
        await scroll_to(page, "#ecosystem", -100)
        await cap(page, "The whole field: every legal job by what you'd do and how much preparation it takes, in plain words.", 5)
        await shot(page, "field")
        await page.click("#save-btn")
        await cap(page, "Save it with the heart to compare later.", 2.5)

        # 7. Discover
        await page.goto(URL + "?d=1#/discover"); await page.wait_for_selector(".chipset .ch"); await page.wait_for_timeout(600)
        await cap(page, "No idea what you want? Discover mode asks what you like, and the more you share, the more specific it gets.", 4)
        clicks = [("strengths", "Caring for people or animals"), ("strengths", "Science & experiments"), ("strengths", "Explaining things to others"),
                  ("subjects_like", "Biology"), ("subjects_like", "Chemistry"), ("work_with", "People"), ("setting", "Indoors"),
                  ("activity", "Active"), ("values", "Helping others"), ("values", "Job security & growth"), ("max_school_years", "4")]
        for key, v in clicks:
            loc = page.locator(f'.chipset[data-key="{key}"] .ch[data-v="{v}"]')
            await loc.scroll_into_view_if_needed()
            await loc.click(); await page.wait_for_timeout(350)
        await page.fill("#interest-input", "volunteering at the animal shelter"); await page.press("#interest-input", "Enter")
        await page.fill("#interest-input", "swimming"); await page.press("#interest-input", "Enter")
        await page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
        await cap(page, "The meter shows how much they've shared. Fields unlock at 5 inputs, careers at 9, majors and schools at 14.", 4)
        await page.click("#disc-go")
        await cap(page, "A matching engine scores all 774 careers; an AI advisor explains each pick in the student's own terms.", 3)
        await page.wait_for_selector(".dcard", timeout=90000)
        await page.wait_for_timeout(1500)
        await scroll_to(page, "#disc-results", -90)
        await cap(page, "Top fields first, then careers with why they fit, high-school classes, majors and schools in Connecticut.", 5)
        await shot(page, "discover")
        await page.locator(".dcard [data-save]").first.click()
        await page.locator(".dcard [data-save]").nth(1).click()
        await scroll_to(page, ".dcard:nth-child(3)", -100, 1.2)

        # 8. Compare
        await page.goto(URL + "?c=1#/compare"); await page.wait_for_selector(".cmp"); await page.wait_for_timeout(900)
        await cap(page, "Compare saved careers side by side: pay in your state, majors' earnings, growth, schooling, skills, daily life.", 4.5)
        await page.mouse.wheel(0, 600); await page.wait_for_timeout(2500)
        await shot(page, "compare")
        await page.mouse.wheel(0, 700); await page.wait_for_timeout(2500)

        # 9. Map
        await page.goto(URL + "?m=1#/map"); await page.wait_for_selector(".mx"); await page.wait_for_timeout(800)
        await cap(page, "The career map: all 774 careers by field (rows) and main capability (columns).", 3.5)
        await page.locator('.mx-c[data-v="29"][data-c="Helping & teaching"]').click()
        await page.wait_for_timeout(1500)
        await cap(page, "Click any cell to see those careers, then test-drive or save them. Free, no sign-up, about $0.0015 per exploration.", 5)
        await cap(page, "", 0.5)
        await ctx.close()
        await b.close()
    vid = next(vids.glob("*.webm"))
    out = ROOT / "docs" / "demo.webm"
    shutil.move(str(vid), out)
    shutil.rmtree(vids, ignore_errors=True)
    print("saved", out, f"{out.stat().st_size / 1e6:.1f} MB")


asyncio.run(main())

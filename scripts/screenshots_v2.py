"""Screenshots of the v2 features (needs the server on :8000).   python scripts/screenshots_v2.py"""
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "shots"
URL = "http://127.0.0.1:8000/"


async def el(page, sel, name):
    loc = page.locator(sel).first
    await loc.scroll_into_view_if_needed()
    await page.wait_for_timeout(600)
    await loc.screenshot(path=OUT / f"{name}.png")
    print("saved", name)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 860}, device_scale_factor=2)
        await ctx.add_init_script("localStorage.setItem('ctd_state', JSON.stringify('CT'));"
                                  "localStorage.setItem('ctd_garage', JSON.stringify([{id:'23-1011.00',title:'Lawyers'},{id:'23-2011.00',title:'Paralegals and Legal Assistants'},{id:'23-1012.00',title:'Judicial Law Clerks'}]));")
        await ctx.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='.topbar,.section-nav{position:static!important}';document.head.appendChild(s);});")
        page = await ctx.new_page()
        # career page
        await page.goto(URL); await page.wait_for_timeout(1200)
        await page.evaluate("window.ctdStart({career:'lawyer', beliefs:'Lawyers argue in court every day and make $300k right out of school.', likes:'debating'})")
        await page.wait_for_selector("#hood-body table", timeout=120000)
        await page.wait_for_selector(".plain-card", timeout=60000)
        await page.wait_for_selector(".eco-grid", timeout=60000)
        await page.wait_for_selector("#schools table", timeout=60000)
        await page.wait_for_timeout(1000)
        await el(page, "#overview", "v2_overview")
        await page.locator("#pl-next").click(); await page.locator("#pl-next").click()
        await page.wait_for_timeout(900)
        await el(page, "#day", "v2_day")
        await el(page, "#paystages", "v2_paystages")
        await el(page, ".statewrap", "v2_states")
        await el(page, "#study", "v2_study")
        await el(page, "#ecosystem", "v2_ecosystem")
        # compare
        await page.goto(URL + "#/compare"); await page.wait_for_selector(".cmp"); await page.wait_for_timeout(800)
        await el(page, "#compare", "v2_compare")
        # map
        await page.goto(URL + "?m=1#/map"); await page.wait_for_selector(".mx")
        await page.locator('.mx-c[data-v="23"][data-c="Leading & persuading"]').click()
        await page.wait_for_timeout(500)
        await page.screenshot(path=OUT / "v2_map.png", full_page=False)
        await el(page, ".mx-wrap", "v2_matrix")
        # discover
        await page.goto(URL + "?d=1#/discover"); await page.wait_for_selector(".chipset .ch")
        js = """
        const click=(key,v)=>document.querySelector(`.chipset[data-key="${key}"] .ch[data-v="${v}"]`).click();
        ['Caring for people or animals','Science & experiments','Explaining things to others'].forEach(v=>click('strengths',v));
        ['Biology','Chemistry'].forEach(v=>click('subjects_like',v)); click('subjects_dislike','Economics and Accounting');
        click('work_with','People'); click('setting','Indoors'); click('activity','Active');
        ['Helping others','Job security & growth'].forEach(v=>click('values',v)); click('max_school_years','4');
        const inp=document.getElementById('interest-input');
        ['volunteering at the animal shelter','swimming'].forEach(t=>{inp.value=t; inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));});
        document.getElementById('free-text').value='I like helping my grandma with her meds and I am calm when people are stressed.';
        document.getElementById('free-text').dispatchEvent(new Event('input'));"""
        await page.evaluate(js)
        await page.wait_for_timeout(300)
        await page.screenshot(path=OUT / "v2_discover_form.png")
        print("saved v2_discover_form")
        await page.click("#disc-go")
        await page.wait_for_selector(".dcard", timeout=120000)
        await page.wait_for_timeout(2500)
        await el(page, "#disc-results", "v2_discover_results")
        await b.close()

asyncio.run(main())

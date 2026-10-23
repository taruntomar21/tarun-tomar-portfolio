"""Real-browser smoke checks. Use a disposable environment; creates one QA message."""
import argparse
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright


def run():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',default='http://127.0.0.1:5000')
    parser.add_argument('--output',default='artifacts/browser')
    args=parser.parse_args(); base=args.base_url.rstrip('/'); out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    report={'base_url':base,'checks':[],'console_errors':[],'page_errors':[]}
    paths=['/','/about','/projects','/skills','/experience','/resume','/blog','/contact']
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        context=browser.new_context(color_scheme='light',viewport={'width':1440,'height':1000})
        page=context.new_page()
        page.on('pageerror',lambda error:report['page_errors'].append(str(error)))
        page.on('console',lambda msg:report['console_errors'].append(msg.text) if msg.type=='error' else None)
        for width in (360,768,1024,1440):
            page.set_viewport_size({'width':width,'height':1000})
            for path in paths:
                response=page.goto(base+path); page.wait_for_load_state('networkidle')
                assert response.status==200,(width,path,response.status)
                assert page.locator('h1').count()==1,(path,'h1 count')
                dimensions=page.evaluate('({scroll:document.documentElement.scrollWidth,view:innerWidth})')
                assert dimensions['scroll']<=dimensions['view']+1,(width,path,dimensions)
                assert page.locator('main').is_visible()
                report['checks'].append(f'{width}px {path}: HTTP 200, main visible, one h1, no horizontal overflow')
        page.set_viewport_size({'width':360,'height':900}); page.goto(base)
        page.get_by_role('button',name='Open navigation').click()
        assert page.locator('#primary-nav').is_visible()
        page.locator('#primary-nav').get_by_role('link',name='Projects',exact=True).click()
        page.wait_for_url(base+'/projects'); assert not page.locator('#primary-nav').is_visible()
        report['checks'].append('Mobile hamburger opens and project navigation closes it')
        page.goto(base); page.get_by_role('button',name='Switch to dark theme').click(); page.reload()
        assert page.locator('html').get_attribute('data-theme')=='dark'
        report['checks'].append('Theme toggle persists through reload')
        page.set_viewport_size({'width':1440,'height':1000}); page.screenshot(path=str(out/'homepage-dark.png'),full_page=True,animations='disabled')
        page.get_by_role('button',name='Switch to light theme').click(); page.reload()
        page.screenshot(path=str(out/'homepage-desktop.png'),full_page=True,animations='disabled')
        page.screenshot(path=str(out/'homepage-preview.png'),full_page=False,animations='disabled')
        page.set_viewport_size({'width':360,'height':900}); page.screenshot(path=str(out/'homepage-mobile.png'),full_page=True,animations='disabled')
        page.goto(base+'/projects'); page.fill('#project-search','no matching project'); page.get_by_role('button',name='Apply',exact=True).click()
        page.wait_for_function("() => !document.querySelector('#project-results').hasAttribute('aria-busy')")
        assert 'q=no+matching+project' in page.url
        assert page.get_by_role('heading',name='No projects found').is_visible()
        report['checks'].append('AJAX search loading/result state and URL update work')
        page.goto(base+'/contact'); page.fill('#name','QA browser test'); page.fill('#email','qa-browser@example.com'); page.fill('#subject','Browser smoke test'); page.fill('#message','Automated local QA message. Safe to delete.')
        page.get_by_role('button',name='Send message').click(); page.wait_for_function("() => document.querySelector('#contact-status').classList.contains('success')")
        assert 'received' in page.locator('#contact-status').inner_text()
        assert page.locator('#name').input_value()==''
        report['checks'].append('Real JS contact submission saved successfully and form reset')
        # Verify 404 without counting its expected browser network error as an unexpected error.
        known_errors=len(report['console_errors']); response=page.goto(base+'/not-a-real-page')
        assert response.status==404
        report['console_errors']=report['console_errors'][:known_errors]
        report['checks'].append('Custom missing page returns HTTP 404')
        reduced=browser.new_context(reduced_motion='reduce',viewport={'width':360,'height':900})
        rp=reduced.new_page(); rp.goto(base); assert rp.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
        assert rp.locator('html').evaluate("el=>getComputedStyle(el).scrollBehavior")=='auto'
        rp.keyboard.press('Tab'); assert rp.locator('.skip-link').evaluate('el=>el===document.activeElement')
        report['checks'].append('Reduced motion respected; keyboard skip link receives focus')
        # Optional full admin browser journey using credentials supplied by caller, never defaults.
        if os.getenv('BROWSER_ADMIN_EMAIL') and os.getenv('BROWSER_ADMIN_PASSWORD'):
            page.set_viewport_size({'width':1440,'height':1000}); page.goto(base+'/admin/login')
            page.fill('#email',os.environ['BROWSER_ADMIN_EMAIL']); page.fill('#password',os.environ['BROWSER_ADMIN_PASSWORD']); page.get_by_role('button',name='Sign in',exact=True).click(); page.wait_for_url(base+'/admin')
            page.screenshot(path=str(out/'admin-desktop.png'),full_page=True,animations='disabled')
            for width in (360,768,1024,1440):
                page.set_viewport_size({'width':width,'height':1000})
                for path in ['/admin','/admin/projects','/admin/profile','/admin/content/skills','/admin/messages','/admin/blog']:
                    assert page.goto(base+path).status==200
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),(width,path)
            page.goto(base+'/admin/projects/new'); page.fill('#title','QA browser project'); page.fill('#short_description','Temporary browser QA content; not a real personal project.'); page.fill('#technologies','Python, SQL'); page.get_by_role('button',name='Save project').click(); page.wait_for_url(base+'/admin/projects')
            row=page.get_by_role('row').filter(has_text='QA browser project')
            row.get_by_role('button',name='Publish',exact=True).click(); page.wait_for_load_state('networkidle')
            row=page.get_by_role('row').filter(has_text='QA browser project'); row.get_by_role('button',name='Feature',exact=True).click(); page.wait_for_load_state('networkidle')
            page.goto(base); assert page.get_by_role('heading',name='QA browser project').is_visible()
            page.goto(base+'/admin/projects'); row=page.get_by_role('row').filter(has_text='QA browser project'); row.get_by_role('link',name='Edit',exact=True).click(); page.fill('#title','QA browser project edited'); page.get_by_role('button',name='Save project').click(); page.wait_for_url(base+'/admin/projects')
            page.once('dialog',lambda dialog:dialog.dismiss()); page.get_by_role('row').filter(has_text='QA browser project edited').get_by_role('button',name='Delete',exact=True).click()
            assert page.get_by_role('row').filter(has_text='QA browser project edited').count()==1
            page.once('dialog',lambda dialog:dialog.accept()); page.get_by_role('row').filter(has_text='QA browser project edited').get_by_role('button',name='Delete',exact=True).click(); page.wait_for_load_state('networkidle')
            assert page.get_by_role('row').filter(has_text='QA browser project edited').count()==0
            page.goto(base+'/admin'); page.get_by_role('button',name='Sign out',exact=True).click(); page.wait_for_url(base+'/admin/login')
            report['checks'].append('Admin login, four-width admin layouts, create/publish/feature/edit, cancel/confirm delete, logout work in browser')
        assert not report['page_errors'],report['page_errors']
        assert not report['console_errors'],report['console_errors']
        report['checks'].append('No unexpected browser console or JavaScript runtime errors')
        browser.close()
    report['result']='passed'
    (out/'browser-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__': run()

import click
import frappe

from .spa_generator import SPAGenerator
from frappe.commands import get_site, pass_context
from .frappe_ui import add_frappe_ui
from .desk_page import setup_desk_page


@click.command("add-spa")
@click.option("--name", default="dashboard", prompt="Dashboard Name")
@click.option("--app", prompt="App Name")
@click.option(
    "--framework",
    type=click.Choice(["vue", "react"]),
    default="vue",
    prompt="Which framework do you want to use?",
    help="The framework to use for the SPA",
)
@click.option(
    "--typescript",
    default=False,
    prompt="Configure TypeScript?",
    is_flag=True,
    help="Configure with TypeScript",
)
@click.option(
    "--tailwindcss", default=False, is_flag=True, help="Configure tailwindCSS"
)
@click.option(
    "--tailwindcss-v4", default=False, is_flag=True, help="Configure TailwindCSS v4 (React only)"
)
@click.option(
    "--shadcn", default=False, is_flag=True, help="Setup shadcn/ui (React only)"
)
@click.option(
    "--dark-mode", default=False, is_flag=True, help="Setup dark mode with shadcn/ui (React only)"
)
@click.option(
    "--i18n", default=False, is_flag=True, help="Setup i18n for multi-language support (React only)"
)
def generate_spa(framework, name, app, typescript, tailwindcss, tailwindcss_v4, shadcn, dark_mode, i18n):
    if not app:
        click.echo("Please provide an app with --app")
        return
    
    # Chỉ hỏi các options React nếu framework là React
    if framework == "react":
        if not tailwindcss_v4 and not tailwindcss:
            tailwindcss_v4 = click.confirm("Setup TailwindCSS v4?", default=True)
        if not shadcn:
            shadcn = click.confirm("Setup shadcn/ui?", default=False)
        if shadcn and not dark_mode:
            dark_mode = click.confirm("Enable dark mode?", default=True)
        if not i18n:
            i18n = click.confirm("Setup i18n (multi-language)?", default=False)
    
    generator = SPAGenerator(
        framework, name, app, tailwindcss, typescript,
        tailwindcss_v4=tailwindcss_v4,
        shadcn=shadcn,
        dark_mode=dark_mode,
        i18n=i18n
    )
    generator.generate_spa()

@click.command("add-desk-page")
@click.option("--page-name", prompt="Page Name")
@click.option("--app", prompt="App Name")
@click.option(
    "--starter",
    type=click.Choice(["vue", "react"]),
    default="vue",
    prompt="Which framework do you want to use?",
    help="Setup a desk page with the framework of your choice",
)
@pass_context
def add_desk_page(context, app, page_name, starter):
    site = get_site(context)
    frappe.init(site=site)

    try:
        frappe.connect()
        setup_desk_page(site, app, page_name, starter)
    finally:
        frappe.destroy()


commands = [generate_spa, add_frappe_ui, add_desk_page]

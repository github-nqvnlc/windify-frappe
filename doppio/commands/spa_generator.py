import click
import subprocess
import time
import shutil

from pathlib import Path
from .boilerplates import *
from .utils import (
	create_file,
	add_commands_to_root_package_json,
	add_routing_rule_to_hooks,
)


class SPAGenerator:
	def __init__(self, framework, spa_name, app, add_tailwindcss, typescript,
	             tailwindcss_v4=False, shadcn=False, dark_mode=False, i18n=False):
		"""Initialize a new SPAGenerator instance"""
		self.framework = framework
		self.app = app
		self.app_path = Path("../apps") / app
		self.spa_name = spa_name
		self.spa_path: Path = self.app_path / self.spa_name
		self.add_tailwindcss = add_tailwindcss
		self.use_typescript = typescript
		self.tailwindcss_v4 = tailwindcss_v4 and framework == "react"
		self.shadcn = shadcn and framework == "react"
		self.dark_mode = dark_mode and self.shadcn
		self.i18n = i18n and framework == "react"

		self.validate_spa_name()

	def validate_spa_name(self):
		if self.spa_name == self.app:
			click.echo("Dashboard name must not be same as app name", err=True, color=True)
			exit(1)
		
		# Kiểm tra và xử lý nếu thư mục đã tồn tại
		if self.spa_path.exists():
			click.echo(f"⚠️  Directory {self.spa_path} already exists!", err=True)
			response = click.prompt(
				"Do you want to remove it and create a new one? (y/N)",
				default="N",
				type=str
			)
			if response.lower() == 'y':
				click.echo(f"Removing existing directory: {self.spa_path}")
				shutil.rmtree(self.spa_path)
				click.echo("✅ Directory removed")
			else:
				click.echo("Aborting. Please choose a different name or remove the existing directory.", err=True)
				exit(1)

	def generate_spa(self):
		click.echo("Generating spa...")
		try:
			if self.framework == "vue":
				if not self.initialize_vue_vite_project():
					raise Exception("Failed to initialize Vue project")
				self.link_controller_files()
				self.setup_proxy_options()
				self.setup_vue_vite_config()
				self.setup_vue_router()
				self.create_vue_files()

			elif self.framework == "react":
				if not self.initialize_react_vite_project():
					raise Exception("Failed to initialize React project")
				self.setup_proxy_options()
				self.setup_react_vite_config()
				
				# Setup các features cho React trước khi tạo App component
				if self.tailwindcss_v4:
					self.setup_tailwindcss_v4()
				
				if self.shadcn:
					self.setup_shadcn_ui()
					if self.dark_mode:
						self.setup_dark_mode()
				
				if self.i18n:
					self.setup_i18n()
				
				# Tạo App component sau khi tất cả features đã được setup
				self.create_react_files()
		except Exception as e:
			click.echo(f"❌ Error during SPA generation: {e}", err=True)
			click.echo("Aborting generation process.", err=True)
			raise

		# Common to all frameworks
		add_commands_to_root_package_json(self.app, self.spa_name)
		self.create_www_directory()
		self.add_csrf_to_html()

		if self.add_tailwindcss and not self.tailwindcss_v4:
			self.setup_tailwindcss()

		# Đảm bảo tsconfig paths được update sau khi tất cả setup xong
		if self.framework == "react" and self.use_typescript:
			self._update_tsconfig_paths()

		add_routing_rule_to_hooks(self.app, self.spa_name)

		click.echo(f"Run: cd {self.spa_path.absolute().resolve()} && npm run dev")
		click.echo("to start the development server and visit: http://<site>:8080")

	def setup_tailwindcss(self):
		# TODO: Convert to yarn command
		# npm install -D tailwindcss@latest postcss@latest autoprefixer@latest
		subprocess.run(
			[
				"npm",
				"install",
				"-D",
				"tailwindcss@latest",
				"postcss@latest",
				"autoprefixer@latest",
			],
			cwd=self.spa_path,
		)

		# npx tailwindcss init -p
		subprocess.run(["npx", "tailwindcss", "init", "-p"], cwd=self.spa_path)

		# Create an index.css file
		index_css_path: Path = self.spa_path / "src/index.css"

		# Add boilerplate code
		INDEX_CSS_BOILERPLATE = """@tailwind base;
@tailwind components;
@tailwind utilities;
	"""

		create_file(index_css_path, INDEX_CSS_BOILERPLATE)

		# Populate content property in tailwind config file
		# the extension of config can be .js or .ts, so we need to check for both
		tailwind_config_path: Path = self.spa_path / "tailwind.config.js"
		if not tailwind_config_path.exists():
			tailwind_config_path = self.spa_path / "tailwind.config.ts"

		tailwind_config_path: Path = self.spa_path / "tailwind.config.js"
		tailwind_config = tailwind_config_path.read_text()
		tailwind_config = tailwind_config.replace(
			"content: [],", 'content: ["./src/**/*.{html,jsx,tsx,vue,js,ts}"],'
		)
		tailwind_config_path.write_text(tailwind_config)

	def create_vue_files(self):
		app_vue = self.spa_path / "src/App.vue"
		create_file(app_vue, APP_VUE_BOILERPLATE)

		views_dir: Path = self.spa_path / "src/views"
		if not views_dir.exists():
			views_dir.mkdir()

		home_vue = views_dir / "Home.vue"
		login_vue = views_dir / "Login.vue"

		create_file(home_vue, HOME_VUE_BOILERPLATE)
		create_file(login_vue, LOGIN_VUE_BOILERPLATE)

	def setup_vue_router(self):
		# Setup vue router
		router_dir_path: Path = self.spa_path / "src/router"

		# Create router directory
		router_dir_path.mkdir()

		# Create files
		router_index_file = router_dir_path / "index.js"
		create_file(
			router_index_file, ROUTER_INDEX_BOILERPLATE.replace("{{name}}", self.spa_name)
		)

		auth_routes_file = router_dir_path / "auth.js"
		create_file(auth_routes_file, AUTH_ROUTES_BOILERPLATE)

	def initialize_vue_vite_project(self):
		# Run "yarn create vite {name} --template vue"
		click.echo("Scaffolding Vue project...")
		click.echo("⏳ This may take a few moments, please wait...")
		template = "vue-ts" if self.use_typescript else "vue"
		
		# Chạy yarn create vite với real-time output
		click.echo(f"Running: yarn create vite {self.spa_name} --template {template} --no-interactive")
		try:
			process = subprocess.Popen(
				["yarn", "create", "vite", self.spa_name, "--template", template, "--no-interactive"],
				cwd=self.app_path,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,
				text=True,
				bufsize=1,
				universal_newlines=True
			)
			
			# Hiển thị output real-time
			for line in process.stdout:
				line = line.strip()
				if line:
					click.echo(f"  {line}")
			
			process.wait()
			
			if process.returncode != 0:
				click.echo(f"❌ Error scaffolding project (exit code: {process.returncode})", err=True)
				return False
		except Exception as e:
			click.echo(f"❌ Exception during scaffolding: {e}", err=True)
			return False
		
		# Đợi cho đến khi thư mục được tạo (với timeout)
		click.echo("Waiting for project directory to be created...")
		max_retries = 20  # Tăng số lần retry
		retry_count = 0
		while not self.spa_path.exists() and retry_count < max_retries:
			time.sleep(0.5)
			retry_count += 1
		
		if not self.spa_path.exists():
			click.echo(f"❌ Error: Project directory not created: {self.spa_path}", err=True)
			click.echo(f"   This might be because the directory already exists or yarn create vite failed.", err=True)
			return False
		
		click.echo(f"✅ Project directory created: {self.spa_path}")
		
		# Đợi thêm một chút để đảm bảo tất cả files đã được tạo
		time.sleep(1)
		
		# Kiểm tra package.json đã được tạo chưa
		package_json = self.spa_path / "package.json"
		if not package_json.exists():
			click.echo(f"❌ Error: package.json not found in {self.spa_path}", err=True)
			return False

		# Install router and other npm packages
		click.echo("📦 Installing dependencies (this may take a while)...")
		try:
			process = subprocess.Popen(
				["yarn", "add", "vue-router@^4", "socket.io-client@^4.5.1"],
				cwd=self.spa_path,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,
				text=True,
				bufsize=1,
				universal_newlines=True
			)
			
			for line in process.stdout:
				line = line.strip()
				if line and not line.startswith("$"):
					click.echo(f"  {line}")
			
			process.wait()
			
			if process.returncode != 0:
				click.echo(f"❌ Error installing dependencies (exit code: {process.returncode})", err=True)
				return False
		except Exception as e:
			click.echo(f"❌ Exception installing dependencies: {e}", err=True)
			return False
		
		click.echo("✅ Dependencies installed successfully")
		return True

	def link_controller_files(self):
		# Link controller files in main.js/main.ts
		print("Linking controller files...")
		main_js: Path = self.app_path / (
			f"{self.spa_name}/src/main.ts"
			if self.use_typescript
			else f"{self.spa_name}/src/main.js"
		)

		if main_js.exists():
			with main_js.open("w") as f:
				boilerplate = MAIN_JS_BOILERPLATE

				# Add css import
				if self.add_tailwindcss:
					boilerplate = "import './index.css';\n" + boilerplate

				f.write(boilerplate)
		else:
			click.echo("src/main.js not found!")
			return

	def setup_proxy_options(self):
		# Setup proxy options file
		proxy_options_file: Path = self.spa_path / (
			"proxyOptions.ts" if self.use_typescript else "proxyOptions.js"
		)
		click.echo(f"Creating proxy options file: {proxy_options_file}")
		create_file(proxy_options_file, PROXY_OPTIONS_BOILERPLATE)
		click.echo(f"✅ Proxy options file created at {proxy_options_file}")

	def setup_vue_vite_config(self):
		vite_config_file: Path = self.spa_path / (
			"vite.config.ts" if self.use_typescript else "vite.config.js"
		)
		if not vite_config_file.exists():
			vite_config_file.touch()
		with vite_config_file.open("w") as f:
			boilerplate = VUE_VITE_CONFIG_BOILERPLATE.replace("{{app}}", self.app)
			boilerplate = boilerplate.replace("{{name}}", self.spa_name)
			f.write(boilerplate)

	def create_www_directory(self):
		www_dir_path: Path = self.app_path / f"{self.app}/www"

		if not www_dir_path.exists():
			www_dir_path.mkdir()

	def add_csrf_to_html(self):
		index_html_file_path = self.spa_path / "index.html"
		with index_html_file_path.open("r") as f:
			current_html = f.read()

		# For attaching CSRF Token
		updated_html = current_html.replace(
			"</div>", "</div>\n\t\t<script>window.csrf_token = '{{ frappe.session.csrf_token }}';</script>"
		)

		with index_html_file_path.open("w") as f:
			f.write(updated_html)

	def initialize_react_vite_project(self):
		# Run "yarn create vite {name} --template react"
		click.echo("Scaffolding React project...")
		click.echo("⏳ This may take a few moments, please wait...")
		template = "react-ts" if self.use_typescript else "react"
		
		# Chạy yarn create vite với real-time output
		click.echo(f"Running: yarn create vite {self.spa_name} --template {template} --no-interactive")
		try:
			process = subprocess.Popen(
				["yarn", "create", "vite", self.spa_name, "--template", template, "--no-interactive"],
				cwd=self.app_path,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,
				text=True,
				bufsize=1,
				universal_newlines=True
			)
			
			# Hiển thị output real-time
			for line in process.stdout:
				line = line.strip()
				if line:
					click.echo(f"  {line}")
			
			process.wait()
			
			if process.returncode != 0:
				click.echo(f"❌ Error scaffolding project (exit code: {process.returncode})", err=True)
				return False
		except Exception as e:
			click.echo(f"❌ Exception during scaffolding: {e}", err=True)
			return False
		
		# Đợi cho đến khi thư mục được tạo (với timeout)
		click.echo("Waiting for project directory to be created...")
		max_retries = 20  # Tăng số lần retry
		retry_count = 0
		while not self.spa_path.exists() and retry_count < max_retries:
			time.sleep(0.5)
			retry_count += 1
		
		if not self.spa_path.exists():
			click.echo(f"❌ Error: Project directory not created: {self.spa_path}", err=True)
			click.echo(f"   This might be because the directory already exists or yarn create vite failed.", err=True)
			return False
		
		click.echo(f"✅ Project directory created: {self.spa_path}")
		
		# Đợi thêm một chút để đảm bảo tất cả files đã được tạo
		time.sleep(1)
		
		# Kiểm tra package.json đã được tạo chưa
		package_json = self.spa_path / "package.json"
		if not package_json.exists():
			click.echo(f"❌ Error: package.json not found in {self.spa_path}", err=True)
			return False
		
		# Install dependencies manually
		click.echo("📦 Installing dependencies (this may take a while)...")
		try:
			process = subprocess.Popen(
				["yarn", "install"],
				cwd=self.spa_path,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,
				text=True,
				bufsize=1,
				universal_newlines=True
			)
			
			# Hiển thị output với progress
			for line in process.stdout:
				line = line.strip()
				if line and not line.startswith("$"):  # Skip command echo
					click.echo(f"  {line}")
			
			process.wait()
			
			if process.returncode != 0:
				click.echo(f"❌ Error installing dependencies (exit code: {process.returncode})", err=True)
				return False
		except Exception as e:
			click.echo(f"❌ Exception installing dependencies: {e}", err=True)
			return False

		# Install frappe-react-sdk
		click.echo("📦 Installing frappe-react-sdk...")
		try:
			process = subprocess.Popen(
				["yarn", "add", "frappe-react-sdk"],
				cwd=self.spa_path,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,
				text=True,
				bufsize=1,
				universal_newlines=True
			)
			
			for line in process.stdout:
				line = line.strip()
				if line and not line.startswith("$"):
					click.echo(f"  {line}")
			
			process.wait()
			
			if process.returncode != 0:
				click.echo(f"❌ Error installing frappe-react-sdk (exit code: {process.returncode})", err=True)
				return False
		except Exception as e:
			click.echo(f"❌ Exception installing frappe-react-sdk: {e}", err=True)
			return False
		
		click.echo("✅ Dependencies installed successfully")
		return True

	def setup_react_vite_config(self):
		vite_config_file: Path = self.spa_path / (
			"vite.config.ts" if self.use_typescript else "vite.config.js"
		)
		
		# Always overwrite với config từ Doppio
		click.echo(f"Setting up Vite config: {vite_config_file}")
		with vite_config_file.open("w") as f:
			boilerplate = REACT_VITE_CONFIG_BOILERPLATE.replace("{{app}}", self.app)
			boilerplate = boilerplate.replace("{{name}}", self.spa_name)
			f.write(boilerplate)
		
		click.echo(f"✅ Vite config created at {vite_config_file}")
		
		# Cập nhật tsconfig để hỗ trợ @ alias cho TypeScript
		if self.use_typescript:
			self._update_tsconfig_paths()

	def create_react_files(self):
		app_react = self.spa_path / ("src/App.tsx" if self.use_typescript else "src/App.jsx")
		# Tạo App component với demo UI nếu có features
		if self.tailwindcss_v4 or self.shadcn or self.dark_mode or self.i18n:
			app_content = self._generate_demo_app()
		else:
			app_content = APP_REACT_BOILERPLATE
		create_file(app_react, app_content)
	
	def setup_tailwindcss_v4(self):
		"""Setup TailwindCSS v4 cho React"""
		click.echo("🎨 Setting up TailwindCSS v4...")
		
		# Xóa nội dung của index.css và App.css trước khi setup TailwindCSS
		index_css = self.spa_path / "src/index.css"
		if index_css.exists():
			click.echo("Clearing index.css...")
			with index_css.open("w") as f:
				f.write("")
			click.echo("✅ Cleared index.css")
		
		app_css = self.spa_path / "src/App.css"
		if app_css.exists():
			click.echo("Clearing App.css...")
			with app_css.open("w") as f:
				f.write("")
			click.echo("✅ Cleared App.css")
		
		# Cài đặt dependencies
		try:
			click.echo("Installing TailwindCSS v4...")
			subprocess.run(
				["yarn", "add", "-D", "tailwindcss@latest", "@tailwindcss/postcss@latest", "postcss", "postcss-cli"],
				cwd=self.spa_path,
				check=True
			)
		except subprocess.CalledProcessError as e:
			click.echo(f"❌ Error installing TailwindCSS v4: {e}", err=True)
			return
		
		# Cập nhật vite.config để thêm PostCSS config (không tạo postcss.config.js riêng)
		vite_config_file = self.spa_path / ("vite.config.ts" if self.use_typescript else "vite.config.js")
		if vite_config_file.exists():
			with vite_config_file.open("r") as f:
				content = f.read()
			
			# Thêm import tailwindcss nếu chưa có
			if "import tailwindcss" not in content:
				# Tìm dòng import proxyOptions và thêm sau đó
				if "import proxyOptions" in content:
					content = content.replace(
						"import proxyOptions from './proxyOptions';",
						"import proxyOptions from './proxyOptions';\nimport tailwindcss from '@tailwindcss/postcss';"
					)
				else:
					# Thêm vào đầu file sau các import khác
					import_line = "import tailwindcss from '@tailwindcss/postcss';\n"
					# Tìm dòng cuối cùng của các import
					lines = content.split('\n')
					last_import_idx = 0
					for i, line in enumerate(lines):
						if line.strip().startswith('import '):
							last_import_idx = i
					lines.insert(last_import_idx + 1, import_line)
					content = '\n'.join(lines)
			
			# Thêm css.postcss config nếu chưa có
			if "css:" not in content:
				# Thêm sau resolve section
				content = content.replace(
					"\tresolve: {",
					"\tcss: {\n\t\tpostcss: {\n\t\t\tplugins: [tailwindcss()],\n\t\t},\n\t},\n\tresolve: {"
				)
			
			with vite_config_file.open("w") as f:
				f.write(content)
			click.echo("✅ Updated vite.config.ts with PostCSS configuration")
		
		# Tạo styles.css với TailwindCSS v4
		styles_css = self.spa_path / "src/styles.css"
		styles_content = """@import "tailwindcss";

@theme {
  --color-primary: #3b82f6;
  --color-primary-foreground: #ffffff;
  --color-secondary: #8b5cf6;
  --color-secondary-foreground: #ffffff;
  --color-success: #10b981;
  --color-danger: #ef4444;
  --color-destructive: #ef4444;
  --color-destructive-foreground: #ffffff;
  
  --color-background: #ffffff;
  --color-foreground: #0f172a;
  --color-card: #ffffff;
  --color-card-foreground: #0f172a;
  --color-popover: #ffffff;
  --color-popover-foreground: #0f172a;
  --color-muted: #f1f5f9;
  --color-muted-foreground: #64748b;
  --color-accent: #f1f5f9;
  --color-accent-foreground: #0f172a;
  --color-border: #e2e8f0;
  --color-input: #e2e8f0;
  --color-ring: #3b82f6;
}

@layer components {
  .btn {
    @apply px-4 py-2 rounded-lg font-medium transition-all duration-200;
    @apply focus:outline-none focus:ring-2 focus:ring-offset-2;
    @apply shadow-md hover:shadow-lg active:scale-95;
  }
  
  .btn-primary {
    @apply bg-primary text-primary-foreground hover:bg-primary/90;
    @apply focus:ring-primary;
  }
}

@layer utilities {
  .text-balance {
    text-wrap: balance;
  }
}
"""
		create_file(styles_css, styles_content)
		
		# Import CSS vào main file
		main_file = self.spa_path / ("src/main.tsx" if self.use_typescript else "src/main.jsx")
		if main_file.exists():
			with main_file.open("r") as f:
				content = f.read()
			if "import './styles.css'" not in content:
				content = "import './styles.css';\n" + content
				with main_file.open("w") as f:
					f.write(content)
		
		click.echo("✅ TailwindCSS v4 setup completed")
	
	def setup_shadcn_ui(self):
		"""Setup shadcn/ui"""
		click.echo("🎨 Setting up shadcn/ui...")
		
		# Kiểm tra TailwindCSS v4 đã được setup chưa
		if not self.tailwindcss_v4:
			click.echo("⚠️  TailwindCSS v4 is required for shadcn/ui. Setting up TailwindCSS v4 first...")
			self.setup_tailwindcss_v4()
		
		# Cài đặt shadcn/ui dependencies
		try:
			click.echo("Installing shadcn/ui dependencies...")
			subprocess.run(
				["yarn", "add", "class-variance-authority", "clsx", "tailwind-merge", "lucide-react"],
				cwd=self.spa_path,
				check=True
			)
			
			# Cài đặt React dependencies cho shadcn
			subprocess.run(
				["yarn", "add", "@radix-ui/react-slot", "@radix-ui/react-dialog", "@radix-ui/react-dropdown-menu"],
				cwd=self.spa_path,
				check=True
			)
		except subprocess.CalledProcessError as e:
			click.echo(f"❌ Error installing shadcn/ui dependencies: {e}", err=True)
			return
		
		# Tạo lib/utils.ts hoặc utils.js
		lib_dir = self.spa_path / "src/lib"
		lib_dir.mkdir(exist_ok=True)
		utils_file = lib_dir / ("utils.ts" if self.use_typescript else "utils.js")
		if self.use_typescript:
			utils_content = """import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
"""
		else:
			utils_content = """import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
"""
		create_file(utils_file, utils_content)
		
		# Tạo components.json
		components_json = self.spa_path / "components.json"
		components_content = """{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "src/styles.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
"""
		create_file(components_json, components_content)
		
		# Cập nhật vite.config để hỗ trợ @ alias
		self._update_vite_config_alias()
		
		# Tạo components directory
		components_dir = self.spa_path / "src/components"
		components_dir.mkdir(exist_ok=True)
		ui_dir = components_dir / "ui"
		ui_dir.mkdir(exist_ok=True)
		
		# Tạo button component cơ bản
		button_file = ui_dir / ("button.tsx" if self.use_typescript else "button.jsx")
		if self.use_typescript:
			button_content = """import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
"""
		else:
			button_content = """import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
"""
		create_file(button_file, button_content)
		
		click.echo("✅ shadcn/ui setup completed")
		click.echo("💡 You can add components using: npx shadcn@latest add [component-name]")
	
	def setup_dark_mode(self):
		"""Setup dark mode với shadcn/ui"""
		click.echo("🌙 Setting up dark mode...")
		
		# Cài đặt next-themes
		try:
			subprocess.run(
				["yarn", "add", "next-themes"],
				cwd=self.spa_path,
				check=True
			)
		except subprocess.CalledProcessError as e:
			click.echo(f"❌ Error installing next-themes: {e}", err=True)
			return
		
		# Tạo theme provider
		providers_dir = self.spa_path / "src/providers"
		providers_dir.mkdir(exist_ok=True)
		theme_provider_file = providers_dir / ("theme-provider.tsx" if self.use_typescript else "theme-provider.jsx")
		if self.use_typescript:
			theme_provider_content = """import { createContext, useContext, useEffect, useState } from "react"

type Theme = "dark" | "light" | "system"

type ThemeProviderProps = {
  children: React.ReactNode
  defaultTheme?: Theme
  storageKey?: string
}

type ThemeProviderState = {
  theme: Theme
  setTheme: (theme: Theme) => void
}

const initialState: ThemeProviderState = {
  theme: "system",
  setTheme: () => null,
}

const ThemeProviderContext = createContext<ThemeProviderState>(initialState)

export function ThemeProvider({
  children,
  defaultTheme = "system",
  storageKey = "vite-ui-theme",
  ...props
}: ThemeProviderProps) {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem(storageKey) as Theme) || defaultTheme
  )

  useEffect(() => {
    const root = window.document.documentElement

    root.classList.remove("light", "dark")

    if (theme === "system") {
      const systemTheme = window.matchMedia("(prefers-color-scheme: dark)")
        .matches
        ? "dark"
        : "light"

      root.classList.add(systemTheme)
      return
    }

    root.classList.add(theme)
  }, [theme])

  const value = {
    theme,
    setTheme: (theme: Theme) => {
      localStorage.setItem(storageKey, theme)
      setTheme(theme)
    },
  }

  return (
    <ThemeProviderContext.Provider {...props} value={value}>
      {children}
    </ThemeProviderContext.Provider>
  )
}

export const useTheme = () => {
  const context = useContext(ThemeProviderContext)

  if (context === undefined)
    throw new Error("useTheme must be used within a ThemeProvider")

  return context
}
"""
		else:
			theme_provider_content = """import { createContext, useContext, useEffect, useState } from "react"

const initialState = {
  theme: "system",
  setTheme: () => null,
}

const ThemeProviderContext = createContext(initialState)

export function ThemeProvider({
  children,
  defaultTheme = "system",
  storageKey = "vite-ui-theme",
  ...props
}) {
  const [theme, setTheme] = useState(
    () => localStorage.getItem(storageKey) || defaultTheme
  )

  useEffect(() => {
    const root = window.document.documentElement

    root.classList.remove("light", "dark")

    if (theme === "system") {
      const systemTheme = window.matchMedia("(prefers-color-scheme: dark)")
        .matches
        ? "dark"
        : "light"

      root.classList.add(systemTheme)
      return
    }

    root.classList.add(theme)
  }, [theme])

  const value = {
    theme,
    setTheme: (theme) => {
      localStorage.setItem(storageKey, theme)
      setTheme(theme)
    },
  }

  return (
    <ThemeProviderContext.Provider {...props} value={value}>
      {children}
    </ThemeProviderContext.Provider>
  )
}

export const useTheme = () => {
  const context = useContext(ThemeProviderContext)

  if (context === undefined)
    throw new Error("useTheme must be used within a ThemeProvider")

  return context
}
"""
		create_file(theme_provider_file, theme_provider_content)
		
		# Tạo theme toggle component
		components_ui_dir = self.spa_path / "src/components/ui"
		components_ui_dir.mkdir(exist_ok=True)
		theme_toggle_file = components_ui_dir / ("theme-toggle.tsx" if self.use_typescript else "theme-toggle.jsx")
		theme_toggle_content = """import { Moon, Sun } from "lucide-react"
import { useTheme } from "@/providers/theme-provider"
import { Button } from "./button"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <Button
      variant="outline"
      size="icon"
      onClick={() => setTheme(theme === "light" ? "dark" : "light")}
    >
      <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      <span className="sr-only">Toggle theme</span>
    </Button>
  )
}
"""
		create_file(theme_toggle_file, theme_toggle_content)
		
		# Cập nhật App.tsx để wrap với ThemeProvider
		app_file = self.spa_path / ("src/App.tsx" if self.use_typescript else "src/App.jsx")
		if app_file.exists():
			with app_file.open("r") as f:
				content = f.read()
			
			# Thêm import
			if "ThemeProvider" not in content:
				import_line = 'import { ThemeProvider } from "@/providers/theme-provider"\n'
				content = import_line + content
			
			# Wrap với ThemeProvider
			if "<ThemeProvider>" not in content:
				content = content.replace(
					"<FrappeProvider>",
					"<ThemeProvider>\n      <FrappeProvider>"
				)
				content = content.replace(
					"</FrappeProvider>",
					"</FrappeProvider>\n    </ThemeProvider>"
				)
			
			with app_file.open("w") as f:
				f.write(content)
		
		# Cập nhật styles.css với dark mode variables
		styles_css = self.spa_path / "src/styles.css"
		if styles_css.exists():
			with styles_css.open("r") as f:
				styles_content = f.read()
			
			if "@theme" in styles_content and "dark:" not in styles_content:
				dark_mode_css = """
@media (prefers-color-scheme: dark) {
  @theme {
    --color-background: #0f172a;
    --color-foreground: #f1f5f9;
    --color-card: #1e293b;
    --color-card-foreground: #f1f5f9;
    --color-popover: #1e293b;
    --color-popover-foreground: #f1f5f9;
    --color-muted: #1e293b;
    --color-muted-foreground: #94a3b8;
    --color-accent: #1e293b;
    --color-accent-foreground: #f1f5f9;
    --color-border: #334155;
    --color-input: #334155;
  }
}

.dark {
  --color-background: #0f172a;
  --color-foreground: #f1f5f9;
  --color-card: #1e293b;
  --color-card-foreground: #f1f5f9;
  --color-popover: #1e293b;
  --color-popover-foreground: #f1f5f9;
  --color-muted: #1e293b;
  --color-muted-foreground: #94a3b8;
  --color-accent: #1e293b;
  --color-accent-foreground: #f1f5f9;
  --color-border: #334155;
  --color-input: #334155;
}
"""
				styles_content += dark_mode_css
				with styles_css.open("w") as f:
					f.write(styles_content)
		
		click.echo("✅ Dark mode setup completed")
	
	def setup_i18n(self):
		"""Setup i18n cho đa ngôn ngữ"""
		click.echo("🌍 Setting up i18n...")
		
		# Cài đặt react-i18next
		try:
			click.echo("Installing i18n dependencies...")
			subprocess.run(
				["yarn", "add", "i18next", "react-i18next", "i18next-browser-languagedetector"],
				cwd=self.spa_path,
				check=True
			)
		except subprocess.CalledProcessError as e:
			click.echo(f"❌ Error installing i18n dependencies: {e}", err=True)
			return
		
		# Tạo i18n config
		i18n_dir = self.spa_path / "src/i18n"
		i18n_dir.mkdir(exist_ok=True)
		
		# i18n.ts hoặc i18n.js
		i18n_config_file = i18n_dir / ("index.ts" if self.use_typescript else "index.js")
		i18n_config_content = """import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import en from './locales/en.json'
import vi from './locales/vi.json'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      vi: { translation: vi },
    },
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false,
    },
  })

export default i18n
"""
		create_file(i18n_config_file, i18n_config_content)
		
		# Tạo locales directory
		locales_dir = i18n_dir / "locales"
		locales_dir.mkdir(exist_ok=True)
		
		# en.json
		en_file = locales_dir / "en.json"
		en_content = """{
  "welcome": "Welcome",
  "hello": "Hello",
  "goodbye": "Goodbye"
}
"""
		create_file(en_file, en_content)
		
		# vi.json
		vi_file = locales_dir / "vi.json"
		vi_content = """{
  "welcome": "Chào mừng",
  "hello": "Xin chào",
  "goodbye": "Tạm biệt"
}
"""
		create_file(vi_file, vi_content)
		
		# Import i18n vào main.tsx
		main_file = self.spa_path / ("src/main.tsx" if self.use_typescript else "src/main.jsx")
		if main_file.exists():
			with main_file.open("r") as f:
				content = f.read()
			if "import './i18n'" not in content:
				content = "import './i18n'\n" + content
				with main_file.open("w") as f:
					f.write(content)
		
		# Tạo language switcher component
		components_dir = self.spa_path / "src/components"
		components_dir.mkdir(exist_ok=True)
		lang_switcher_file = components_dir / ("language-switcher.tsx" if self.use_typescript else "language-switcher.jsx")
		if self.use_typescript:
			lang_switcher_content = """import { useTranslation } from 'react-i18next'
import { Button } from './ui/button'

export function LanguageSwitcher() {
  const { i18n } = useTranslation()

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng)
  }

  return (
    <div className="flex gap-2">
      <Button
        variant={i18n.language === 'en' ? 'default' : 'outline'}
        onClick={() => changeLanguage('en')}
      >
        English
      </Button>
      <Button
        variant={i18n.language === 'vi' ? 'default' : 'outline'}
        onClick={() => changeLanguage('vi')}
      >
        Tiếng Việt
      </Button>
    </div>
  )
}
"""
		else:
			lang_switcher_content = """import { useTranslation } from 'react-i18next'
import { Button } from './ui/button'

export function LanguageSwitcher() {
  const { i18n } = useTranslation()

  const changeLanguage = (lng) => {
    i18n.changeLanguage(lng)
  }

  return (
    <div className="flex gap-2">
      <Button
        variant={i18n.language === 'en' ? 'default' : 'outline'}
        onClick={() => changeLanguage('en')}
      >
        English
      </Button>
      <Button
        variant={i18n.language === 'vi' ? 'default' : 'outline'}
        onClick={() => changeLanguage('vi')}
      >
        Tiếng Việt
      </Button>
    </div>
  )
}
"""
		create_file(lang_switcher_file, lang_switcher_content)
		
		click.echo("✅ i18n setup completed")
		click.echo("💡 Use useTranslation() hook in your components to translate text")
		
		# Cập nhật translation files với các keys cho demo
		self._update_i18n_demo_keys()
	
	def _update_i18n_demo_keys(self):
		"""Cập nhật các file i18n với keys cho demo UI"""
		locales_dir = self.spa_path / "src/i18n/locales"
		if not locales_dir.exists():
			return
		
		import json
		
		# Cập nhật en.json
		en_file = locales_dir / "en.json"
		if en_file.exists():
			with en_file.open("r") as f:
				data = json.load(f)
				data.update({
					"tailwindcss_demo": "TailwindCSS Demo",
					"shadcn_demo": "shadcn/ui Demo",
					"dark_mode_demo": "Dark Mode Demo",
					"dark_mode_description": "Toggle between light and dark themes using the button in the header.",
					"theme_aware_content": "This content adapts to the current theme.",
					"i18n_demo": "Internationalization Demo",
					"counter_demo": "Counter Demo"
				})
				with en_file.open("w") as f:
					json.dump(data, f, indent=2)
		
		# Cập nhật vi.json
		vi_file = locales_dir / "vi.json"
		if vi_file.exists():
			with vi_file.open("r") as f:
				data = json.load(f)
				data.update({
					"tailwindcss_demo": "Demo TailwindCSS",
					"shadcn_demo": "Demo shadcn/ui",
					"dark_mode_demo": "Demo Dark Mode",
					"dark_mode_description": "Chuyển đổi giữa theme sáng và tối bằng nút ở header.",
					"theme_aware_content": "Nội dung này tự động thích ứng với theme hiện tại.",
					"i18n_demo": "Demo Đa Ngôn Ngữ",
					"counter_demo": "Demo Bộ Đếm"
				})
				with vi_file.open("w") as f:
					json.dump(data, f, indent=2)
	
	def _generate_demo_app(self):
		"""Tạo App component với giao diện demo để test các tính năng"""
		# Build imports
		imports = ["import { useState } from 'react'", "import { FrappeProvider } from 'frappe-react-sdk'"]
		
		if self.tailwindcss_v4:
			imports.append("import './styles.css'")
		
		if self.shadcn:
			imports.append("import { Button } from '@/components/ui/button'")
		
		if self.dark_mode:
			imports.append("import { ThemeProvider } from '@/providers/theme-provider'")
			imports.append("import { ThemeToggle } from '@/components/ui/theme-toggle'")
		
		if self.i18n:
			imports.append("import { useTranslation } from 'react-i18next'")
			imports.append("import { LanguageSwitcher } from '@/components/language-switcher'")
		
		imports_str = "\n".join(imports)
		
		# Build component body
		component_body = """function App() {
  const [count, setCount] = useState(0)"""
		
		if self.i18n:
			component_body += "\n  const { t } = useTranslation()"
		
		component_body += """

  return (
    <FrappeProvider>"""
		
		if self.dark_mode:
			component_body += """
      <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">"""
		
		component_body += """
        <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
          <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex h-16 items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center">
                    <span className="text-primary-foreground font-bold text-sm">D</span>
                  </div>
                  <h1 className="text-2xl font-bold bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">"""
		
		if self.i18n:
			component_body += "{t('welcome')}"
		else:
			component_body += "Demo Dashboard"
		
		component_body += """</h1>
                </div>
                <div className="flex items-center gap-3">"""
		
		if self.i18n:
			component_body += """
                  <LanguageSwitcher />"""
		
		if self.dark_mode:
			component_body += """
                  <ThemeToggle />"""
		
		component_body += """
                </div>
              </div>
            </div>
          </header>

          <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
            <div className="space-y-6 sm:space-y-8">
"""
		
		# TailwindCSS Demo
		if self.tailwindcss_v4:
			component_body += """              <section className="group relative overflow-hidden rounded-xl border bg-card p-6 sm:p-8 shadow-sm transition-all hover:shadow-md">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-secondary/5 opacity-0 transition-opacity group-hover:opacity-100" />
                <div className="relative">
                  <div className="mb-6 flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center shadow-lg">
                      <span className="text-primary-foreground text-lg">🎨</span>
                    </div>
                    <h2 className="text-2xl font-bold tracking-tight">"""
			if self.i18n:
				component_body += "{t('tailwindcss_demo', 'TailwindCSS Demo')}"
			else:
				component_body += "TailwindCSS v4 Demo"
			component_body += """</h2>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                    <div className="group/card relative overflow-hidden rounded-lg bg-gradient-to-br from-primary to-primary/80 p-6 text-primary-foreground shadow-lg transition-transform hover:scale-105">
                      <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent" />
                      <div className="relative">
                        <p className="font-semibold text-lg mb-1">Primary Color</p>
                        <p className="text-sm opacity-90">Using @theme variables</p>
                      </div>
                    </div>
                    <div className="group/card relative overflow-hidden rounded-lg bg-gradient-to-br from-secondary to-secondary/80 p-6 text-secondary-foreground shadow-lg transition-transform hover:scale-105">
                      <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent" />
                      <div className="relative">
                        <p className="font-semibold text-lg mb-1">Secondary Color</p>
                        <p className="text-sm opacity-90">Custom theme colors</p>
                      </div>
                    </div>
                    <div className="group/card relative overflow-hidden rounded-lg bg-gradient-to-br from-success to-success/80 p-6 text-white shadow-lg transition-transform hover:scale-105">
                      <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent" />
                      <div className="relative">
                        <p className="font-semibold text-lg mb-1">Success Color</p>
                        <p className="text-sm opacity-90">Theme customization</p>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <button className="btn btn-primary shadow-md hover:shadow-lg transition-all hover:scale-105">
                      Primary Button
                    </button>
                    <button className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 text-white font-medium shadow-lg hover:shadow-xl transition-all hover:scale-105 hover:from-blue-600 hover:via-purple-600 hover:to-pink-600">
                      Gradient Button
                    </button>
                  </div>
                </div>
              </section>
"""
		
		# shadcn/ui Demo
		if self.shadcn:
			component_body += """              <section className="group relative overflow-hidden rounded-xl border bg-card p-6 sm:p-8 shadow-sm transition-all hover:shadow-md">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-secondary/5 opacity-0 transition-opacity group-hover:opacity-100" />
                <div className="relative">
                  <div className="mb-6 flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center shadow-lg">
                      <span className="text-primary-foreground text-lg">✨</span>
                    </div>
                    <h2 className="text-2xl font-bold tracking-tight">"""
			if self.i18n:
				component_body += "{t('shadcn_demo', 'shadcn/ui Demo')}"
			else:
				component_body += "shadcn/ui Components Demo"
			component_body += """</h2>
                  </div>
                  <div className="mb-6">
                    <p className="text-sm text-muted-foreground mb-4">Button Variants</p>
                    <div className="flex flex-wrap gap-3">
                      <Button variant="default" className="shadow-md hover:shadow-lg transition-all">Default</Button>
                      <Button variant="secondary" className="shadow-md hover:shadow-lg transition-all">Secondary</Button>
                      <Button variant="outline" className="shadow-md hover:shadow-lg transition-all">Outline</Button>
                      <Button variant="ghost" className="hover:shadow-md transition-all">Ghost</Button>
                      <Button variant="destructive" className="shadow-md hover:shadow-lg transition-all">Destructive</Button>
                      <Button variant="link" className="hover:underline">Link</Button>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-4">Button Sizes</p>
                    <div className="flex flex-wrap items-center gap-3">
                      <Button size="sm" className="shadow-md hover:shadow-lg transition-all">Small</Button>
                      <Button size="default" className="shadow-md hover:shadow-lg transition-all">Default</Button>
                      <Button size="lg" className="shadow-md hover:shadow-lg transition-all">Large</Button>
                    </div>
                  </div>
                </div>
              </section>
"""
		
		# Dark Mode Demo
		if self.dark_mode:
			component_body += """              <section className="group relative overflow-hidden rounded-xl border bg-card p-6 sm:p-8 shadow-sm transition-all hover:shadow-md">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-secondary/5 opacity-0 transition-opacity group-hover:opacity-100" />
                <div className="relative">
                  <div className="mb-6 flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center shadow-lg">
                      <span className="text-primary-foreground text-lg">🌙</span>
                    </div>
                    <h2 className="text-2xl font-bold tracking-tight">"""
			if self.i18n:
				component_body += "{t('dark_mode_demo', 'Dark Mode Demo')}"
			else:
				component_body += "Dark Mode Demo"
			component_body += """</h2>
                  </div>
                  <p className="text-muted-foreground mb-6 leading-relaxed">
                    """
			if self.i18n:
				component_body += "{t('dark_mode_description', 'Toggle between light and dark themes using the button in the header.')}"
			else:
				component_body += "Toggle between light and dark themes using the button in the header."
			component_body += """
                  </p>
                  <div className="rounded-lg border-2 border-dashed bg-muted/50 p-6 backdrop-blur-sm">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="h-2 w-2 rounded-full bg-primary animate-pulse" />
                      <p className="font-medium text-foreground">"""
			if self.i18n:
				component_body += "{t('theme_aware_content', 'This content adapts to the current theme.')}"
			else:
				component_body += "This content adapts to the current theme."
			component_body += """</p>
                    </div>
                    <p className="text-sm text-muted-foreground ml-5">
                      The background, text colors, and borders automatically adjust based on your theme preference.
                    </p>
                  </div>
                </div>
              </section>
"""
		
		# i18n Demo
		if self.i18n:
			component_body += """              <section className="group relative overflow-hidden rounded-xl border bg-card p-6 sm:p-8 shadow-sm transition-all hover:shadow-md">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-secondary/5 opacity-0 transition-opacity group-hover:opacity-100" />
                <div className="relative">
                  <div className="mb-6 flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center shadow-lg">
                      <span className="text-primary-foreground text-lg">🌍</span>
                    </div>
                    <h2 className="text-2xl font-bold tracking-tight">"""
			component_body += "{t('i18n_demo', 'Internationalization Demo')}"
			component_body += """</h2>
                  </div>
                  <div className="space-y-4">
                    <div className="rounded-lg bg-muted/50 p-4 border">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-lg">🇬🇧</span>
                        <span className="font-semibold text-sm text-muted-foreground">English</span>
                      </div>
                      <p className="text-foreground">
                        <strong className="text-primary">"""
			component_body += "{t('hello')}"
			component_body += """</strong> - Hello
                      </p>
                      <p className="text-foreground mt-1">
                        <strong className="text-primary">"""
			component_body += "{t('goodbye')}"
			component_body += """</strong> - Goodbye
                      </p>
                    </div>
                    <div className="rounded-lg bg-muted/50 p-4 border">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-lg">🇻🇳</span>
                        <span className="font-semibold text-sm text-muted-foreground">Tiếng Việt</span>
                      </div>
                      <p className="text-foreground">
                        <strong className="text-primary">"""
			component_body += "{t('hello')}"
			component_body += """</strong> - Xin chào
                      </p>
                      <p className="text-foreground mt-1">
                        <strong className="text-primary">"""
			component_body += "{t('goodbye')}"
			component_body += """</strong> - Tạm biệt
                      </p>
                    </div>
                  </div>
                </div>
              </section>
"""
		
		# Counter Demo
		component_body += """              <section className="group relative overflow-hidden rounded-xl border bg-card p-6 sm:p-8 shadow-sm transition-all hover:shadow-md">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-secondary/5 opacity-0 transition-opacity group-hover:opacity-100" />
                <div className="relative">
                  <div className="mb-6 flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center shadow-lg">
                      <span className="text-primary-foreground text-lg">🔢</span>
                    </div>
                    <h2 className="text-2xl font-bold tracking-tight">"""
		if self.i18n:
			component_body += "{t('counter_demo', 'Counter Demo')}"
		else:
			component_body += "Counter Demo"
		component_body += """</h2>
                  </div>
                  <div className="flex flex-col items-center justify-center gap-6 rounded-lg bg-gradient-to-br from-muted/50 to-muted/30 p-8 border-2 border-dashed">
                    <div className="text-6xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                      {count}
                    </div>
                    <div className="flex items-center gap-4">
"""
		if self.shadcn:
			component_body += """                      <Button 
                        onClick={() => setCount(count - 1)} 
                        variant="outline" 
                        size="lg"
                        className="h-12 w-12 rounded-full shadow-md hover:shadow-lg transition-all hover:scale-110"
                      >
                        -
                      </Button>
                      <Button 
                        onClick={() => setCount(count + 1)}
                        size="lg"
                        className="h-12 w-12 rounded-full shadow-md hover:shadow-lg transition-all hover:scale-110"
                      >
                        +
                      </Button>"""
		else:
			component_body += """                      <button 
                        onClick={() => setCount(count - 1)}
                        className="h-12 w-12 rounded-full border-2 border-primary/20 bg-background hover:bg-primary hover:text-primary-foreground hover:border-primary shadow-md hover:shadow-lg transition-all hover:scale-110 font-bold text-lg"
                      >
                        -
                      </button>
                      <button 
                        onClick={() => setCount(count + 1)}
                        className="h-12 w-12 rounded-full bg-gradient-to-br from-primary to-primary/80 text-primary-foreground hover:from-primary/90 hover:to-primary/70 shadow-md hover:shadow-lg transition-all hover:scale-110 font-bold text-lg"
                      >
                        +
                      </button>"""
		
		component_body += """
                    </div>
                  </div>
                </div>
              </section>
            </div>
          </main>
        </div>"""
		
		if self.dark_mode:
			component_body += """
      </ThemeProvider>"""
		
		component_body += """
    </FrappeProvider>
  )
}

export default App"""
		
		return imports_str + "\n\n" + component_body
	
	def _update_vite_config_alias(self):
		"""Cập nhật vite.config để thêm @ alias nếu chưa có"""
		vite_config_file = self.spa_path / ("vite.config.ts" if self.use_typescript else "vite.config.js")
		if not vite_config_file.exists():
			return
		
		with vite_config_file.open("r") as f:
			content = f.read()
		
		# Kiểm tra xem đã có @ alias chưa (kiểm tra cả single và double quotes)
		has_alias = ("'@':" in content or '"@":' in content or "'@/':" in content or '"@/":' in content)
		
		if not has_alias:
			# Đảm bảo đã import path
			if "import path" not in content:
				# Tìm vị trí để thêm import path
				if "import { defineConfig }" in content:
					content = content.replace(
						"import { defineConfig }",
						"import path from 'path';\nimport { defineConfig }"
					)
				elif "import" in content:
					# Thêm sau dòng import cuối cùng
					lines = content.split('\n')
					last_import_idx = 0
					for i, line in enumerate(lines):
						if line.strip().startswith('import '):
							last_import_idx = i
					lines.insert(last_import_idx + 1, "import path from 'path';")
					content = '\n'.join(lines)
				else:
					content = "import path from 'path';\n" + content
			
			# Thêm @ alias vào resolve
			if "resolve:" in content:
				# Kiểm tra xem resolve đã có alias chưa
				if "alias:" not in content or ("resolve: {" in content and "alias:" not in content.split("resolve: {")[1].split("}")[0]):
					content = content.replace(
						"resolve: {",
						"resolve: {\n\t\talias: {\n\t\t\t'@': path.resolve(__dirname, './src')\n\t\t},"
					)
			else:
				# Thêm resolve section trước plugins hoặc server
				if "plugins:" in content:
					content = content.replace(
						"\tplugins:",
						"\tresolve: {\n\t\talias: {\n\t\t\t'@': path.resolve(__dirname, './src')\n\t\t}\n\t},\n\tplugins:"
					)
				elif "server:" in content:
					content = content.replace(
						"\tserver:",
						"\tresolve: {\n\t\talias: {\n\t\t\t'@': path.resolve(__dirname, './src')\n\t\t}\n\t},\n\tserver:"
					)
				else:
					# Thêm vào cuối config object trước dấu đóng ngoặc
					content = content.replace(
						"});",
						"\tresolve: {\n\t\talias: {\n\t\t\t'@': path.resolve(__dirname, './src')\n\t\t}\n\t},\n});"
					)
			
			with vite_config_file.open("w") as f:
				f.write(content)
			click.echo("✅ Updated vite.config with @ alias")
	
	def _update_tsconfig_paths(self):
		"""Cập nhật tsconfig.app.json để thêm paths mapping cho @ alias"""
		tsconfig_app_file = self.spa_path / "tsconfig.app.json"
		if not tsconfig_app_file.exists():
			click.echo("⚠️  tsconfig.app.json not found, skipping paths update", err=True)
			return
		
		import json
		import re
		
		try:
			with tsconfig_app_file.open("r", encoding="utf-8") as f:
				content = f.read()
			
			# Loại bỏ comments trong JSON (tsconfig.json cho phép comments)
			# Loại bỏ single-line comments //
			content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
			# Loại bỏ multi-line comments /* */
			content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
			
			config = json.loads(content)
			
			# Đảm bảo có compilerOptions
			if "compilerOptions" not in config:
				config["compilerOptions"] = {}
			
			# Đảm bảo có types với vite/client (không làm mất cấu hình hiện có)
			if "types" not in config["compilerOptions"]:
				config["compilerOptions"]["types"] = ["vite/client"]
			elif "vite/client" not in config["compilerOptions"].get("types", []):
				types_list = config["compilerOptions"].get("types", [])
				if isinstance(types_list, list):
					types_list.append("vite/client")
					config["compilerOptions"]["types"] = types_list
			
			# Đảm bảo có skipLibCheck (để tránh lỗi type definitions)
			if "skipLibCheck" not in config["compilerOptions"]:
				config["compilerOptions"]["skipLibCheck"] = True
			
			# Luôn đảm bảo có baseUrl (cần thiết cho paths mapping)
			config["compilerOptions"]["baseUrl"] = "."
			
			# Thêm paths nếu chưa có
			if "paths" not in config["compilerOptions"]:
				config["compilerOptions"]["paths"] = {}
			
			# Luôn đảm bảo có @/* alias (ghi đè nếu đã có để đảm bảo đúng)
			config["compilerOptions"]["paths"]["@/*"] = ["./src/*"]
			
			# Ghi lại file với format đẹp
			with tsconfig_app_file.open("w", encoding="utf-8") as f:
				json.dump(config, f, indent=2, ensure_ascii=False)
				f.write("\n")
			
			click.echo("✅ Updated tsconfig.app.json with @ alias paths")
		except json.JSONDecodeError as e:
			click.echo(f"⚠️  Warning: Could not parse tsconfig.app.json: {e}", err=True)
			click.echo(f"   File content may be corrupted. Please check manually.", err=True)
		except Exception as e:
			click.echo(f"⚠️  Warning: Could not update tsconfig.app.json: {e}", err=True)

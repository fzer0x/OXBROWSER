import sys
import os
import glob

# Ensure virtual environment packages (venv) are automatically included in sys.path across Windows, Linux, and macOS
base_project_dir = os.path.dirname(os.path.abspath(__file__))
venv_patterns = [
    os.path.join(base_project_dir, "venv", "lib", "python*", "site-packages"),
    os.path.join(base_project_dir, "venv", "Lib", "site-packages"),
    os.path.join(base_project_dir, "venv", "Lib", "python*", "site-packages"),
    os.path.join(base_project_dir, ".venv", "lib", "python*", "site-packages"),
    os.path.join(base_project_dir, ".venv", "Lib", "site-packages"),
]
for pattern in venv_patterns:
    for sp in glob.glob(pattern):
        if sp not in sys.path:
            sys.path.insert(0, sp)

import asyncio
# Configure Windows event loop policy for optimal qasync & subprocess compatibility
if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
import qasync

import config
from storage.profile_manager import ProfileManager
from storage.proxy_manager import ProxyManager
from engine.browser import BrowserLauncher
from api.server import RestApiServer
from engine.lifecycle import GlobalLifecycleManager
from ui.theme import DARK_STYLESHEET
from ui.main_window import MainWindow

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logging.getLogger("aiohttp.server").setLevel(logging.WARNING)
logging.getLogger("aiohttp.web").setLevel(logging.WARNING)
logging.getLogger("ProxyTunnel").setLevel(logging.WARNING)
logger = logging.getLogger("Main")

async def async_main(app: QApplication):
    logger.info(f"Starting {config.APP_NAME} v{config.APP_VERSION} on {config.HOST_OS_NAME}...")
    lifecycle = GlobalLifecycleManager.get_instance()
    lifecycle.register_signal_handlers(asyncio.get_running_loop())

    # Initialize Core Managers
    profile_manager = ProfileManager()
    proxy_manager = ProxyManager()
    launcher = BrowserLauncher(profile_manager)
    
    # If no profiles exist, create a default sample profile matching host platform
    if not profile_manager.list_profiles():
        profile_manager.create_profile(
            profile_manager.create_default_profile_data("Default Profile", os_type=config.HOST_OS)
        )

    # Start Local Automation REST API
    api_server = RestApiServer(profile_manager, launcher, proxy_manager=proxy_manager)
    await api_server.start()

    # Register with lifecycle manager for deterministic async cleanup
    lifecycle.register_async_cleanup(launcher.stop_all_profiles)
    lifecycle.register_async_cleanup(api_server.stop)

    # Create & Show Main Window
    window = MainWindow(profile_manager, launcher, proxy_manager=proxy_manager)
    window.show()

    logger.info(f"{config.APP_NAME} started successfully on {config.HOST_OS_NAME}.")

    # Keep running until main window is closed or shutdown signal received
    close_event = asyncio.Event()

    def on_close():
        if not close_event.is_set():
            close_event.set()

    window.closing.connect(on_close)
    
    try:
        # Wait for window close or lifecycle shutdown event
        shutdown_waiter = asyncio.create_task(lifecycle.shutdown_event.wait())
        close_waiter = asyncio.create_task(close_event.wait())
        
        done, pending = await asyncio.wait(
            [shutdown_waiter, close_waiter],
            return_when=asyncio.FIRST_COMPLETED
        )
        for p in pending:
            p.cancel()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        logger.info(f"Shutting down {config.APP_NAME} services...")
        await lifecycle.request_shutdown("Application main loop exit")

def main():
    app = QApplication(sys.argv)
    if isinstance(app, QApplication):
        app.setStyleSheet(DARK_STYLESHEET)
        icon_path = os.path.join(os.path.dirname(__file__), "ui", "assets", "icons", "logo.svg")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    def silent_shutdown_exception_handler(loop, context):
        msg = str(context.get("message", ""))
        exc = str(context.get("exception", ""))
        full_err = f"{msg} {exc}"
        if "is not the running loop" in full_err or "pending" in full_err:
            return
        try:
            loop.default_exception_handler(context)
        except Exception:
            pass

    loop.set_exception_handler(silent_shutdown_exception_handler)

    try:
        loop.run_until_complete(async_main(app))
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    except RuntimeError as re:
        if "Event loop stopped before Future completed" in str(re) or "Event loop is closed" in str(re):
            pass
        else:
            logger.exception(f"Unhandled runtime exception: {re}")
    except Exception as e:
        logger.exception(f"Unhandled application exception: {e}")


if __name__ == "__main__":
    main()
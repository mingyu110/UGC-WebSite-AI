"""
Browser Tool

Uses strands_tools AgentCoreBrowser for browsing reference websites.
This integrates with AWS Bedrock AgentCore's browser service.

IMPORTANT: Before using this tool, you must:
1. Create a Browser Tool in AWS Bedrock AgentCore Console
2. Set the AGENTCORE_BROWSER_ID environment variable to the Browser Tool ID

Reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html

The browser tool runs in the AgentCore Runtime and provides:
- Cloud-based browser automation (Chromium)
- Web page content extraction
- Screenshot capture
- Design element analysis
- Session recording and observability
"""

import logging
import os

from strands.tools import tool

logger = logging.getLogger(__name__)

# Browser configuration from environment
BROWSER_ID = os.environ.get("AGENTCORE_BROWSER_ID", "")
REGION = os.environ.get("AWS_REGION", "us-east-1")

# Global browser instance
_browser = None
_browser_type = None


def get_browser():
    """
    Get or create the AgentCore Browser instance.

    Uses AgentCoreBrowser for AWS Bedrock AgentCore Runtime deployment.
    Requires AGENTCORE_BROWSER_ID environment variable to be set.

    Returns:
        tuple: (browser_instance, browser_type)

    Raises:
        ValueError: If AGENTCORE_BROWSER_ID is not configured
    """
    global _browser, _browser_type

    if _browser is not None:
        print(f"[BROWSER_TOOL] Returning existing browser instance, type: {_browser_type}")
        return _browser, _browser_type

    if not BROWSER_ID:
        error_msg = (
            "AGENTCORE_BROWSER_ID environment variable is not set. "
            "Please create a Browser Tool in AWS Bedrock AgentCore Console "
            "and set the Browser Tool ID to AGENTCORE_BROWSER_ID."
        )
        print(f"[BROWSER_TOOL] ERROR: {error_msg}")
        raise ValueError(error_msg)

    try:
        print(f"[BROWSER_TOOL] Creating AgentCoreBrowser with identifier={BROWSER_ID}, region={REGION}")
        from strands_tools.browser import AgentCoreBrowser

        # Create AgentCoreBrowser with required identifier parameter
        # Reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html
        _browser = AgentCoreBrowser(
            region=REGION,
            identifier=BROWSER_ID,  # Browser Tool ID from AWS Console
        )
        _browser_type = "agentcore"
        print(f"[BROWSER_TOOL] AgentCoreBrowser created successfully")
        logger.info(f"Using AgentCoreBrowser (identifier={BROWSER_ID})")
        return _browser, _browser_type
    except Exception as e:
        import traceback
        print(f"[BROWSER_TOOL] Failed to create AgentCoreBrowser: {e}")
        print(f"[BROWSER_TOOL] Traceback:\n{traceback.format_exc()}")
        raise


def get_native_browser_tool():
    """
    Get the native AgentCoreBrowser tool for direct use with Agent.

    This returns the .browser attribute which can be passed directly
    to Agent's tools parameter for native integration.

    Usage in agentcore_handler.py:
        browser_tool = get_native_browser_tool()
        if browser_tool:
            agent = Agent(tools=[browser_tool], ...)

    Returns:
        The native browser tool or None if not available
    """
    try:
        browser, browser_type = get_browser()
        if browser and browser_type == "agentcore":
            return browser.browser
    except ValueError:
        # BROWSER_ID not configured
        print("[BROWSER_TOOL] Native browser tool not available (AGENTCORE_BROWSER_ID not set)")
    except Exception as e:
        print(f"[BROWSER_TOOL] Failed to get native browser tool: {e}")
    return None


@tool
def browse_url(
    url: str,
    extract_content: bool = True,
    take_screenshot: bool = False,
    session_name: str = "ugc-browser-session",
) -> dict:
    """
    Browse a URL using AgentCore Browser.

    Navigate to a web page and extract content.
    Useful for gathering reference materials and design inspiration.

    Args:
        url: The URL to navigate to
        extract_content: Whether to extract page content
        take_screenshot: Whether to capture a screenshot
        session_name: Browser session name for AgentCore

    Returns:
        dict containing:
            - success: Whether navigation was successful
            - url: Final URL (after any redirects)
            - title: Page title
            - content: Page HTML content (if extract_content=True)
            - text: Page text content (if extract_content=True)
            - screenshot: Screenshot data (if take_screenshot=True)
    """
    try:
        browser, _ = get_browser()

        # Initialize session first
        browser.browser(browser_input={
            "action": {
                "type": "init_session",
                "session_name": session_name,
                "description": "UGC AI browsing session"
            }
        })

        # Navigate to URL
        browser.browser(browser_input={
            "action": {
                "type": "navigate",
                "url": url,
                "session_name": session_name
            }
        })

        response = {
            "success": True,
            "url": url,
        }

        if extract_content:
            # Get HTML content
            html_result = browser.browser(browser_input={
                "action": {
                    "type": "get_html",
                    "selector": "body",
                    "session_name": session_name
                }
            })
            response["content"] = html_result.get("html", "")

            # Get text content
            text_result = browser.browser(browser_input={
                "action": {
                    "type": "get_text",
                    "selector": "body",
                    "session_name": session_name
                }
            })
            response["text"] = text_result.get("text", "")

            # Get title via evaluate
            title_result = browser.browser(browser_input={
                "action": {
                    "type": "evaluate",
                    "script": "document.title",
                    "session_name": session_name
                }
            })
            response["title"] = title_result.get("result", "")

        if take_screenshot:
            screenshot_result = browser.browser(browser_input={
                "action": {
                    "type": "screenshot",
                    "session_name": session_name
                }
            })
            response["screenshot"] = screenshot_result.get("screenshot", "")

        return response

    except Exception as e:
        logger.error(f"Browse error: {e}")
        return {
            "success": False,
            "error": str(e),
            "url": url,
        }


@tool
def extract_design_elements(url: str, session_name: str = "ugc-design-session") -> dict:
    """
    Extract design elements from a reference website.

    Analyzes a website to extract design inspiration including:
    - Color palette
    - Typography (fonts, sizes)
    - Layout structure
    - Key components

    Args:
        url: The reference website URL
        session_name: Browser session name for AgentCore

    Returns:
        dict containing:
            - success: Whether extraction was successful
            - colors: List of colors used on the page
            - fonts: List of fonts used
            - layout: Layout type detected
            - components: Common UI components found
    """
    import traceback
    print(f"[BROWSER_TOOL] Starting extract_design_elements for URL: {url}")

    try:
        print("[BROWSER_TOOL] Getting browser instance...")
        browser, browser_type = get_browser()
        print(f"[BROWSER_TOOL] Got browser instance, type: {browser_type}")

        # Initialize session and navigate
        print(f"[BROWSER_TOOL] Initializing browser session: {session_name}")
        try:
            init_result = browser.browser(browser_input={
                "action": {
                    "type": "init_session",
                    "session_name": session_name,
                    "description": "Design extraction session"
                }
            })
            print(f"[BROWSER_TOOL] Session init result: {init_result}")
        except Exception as init_err:
            print(f"[BROWSER_TOOL] Session init error: {init_err}")
            import traceback
            print(f"[BROWSER_TOOL] Init traceback:\n{traceback.format_exc()}")
            raise

        print(f"[BROWSER_TOOL] Navigating to URL: {url}")
        try:
            nav_result = browser.browser(browser_input={
                "action": {
                    "type": "navigate",
                    "url": url,
                    "session_name": session_name
                }
            })
            print(f"[BROWSER_TOOL] Navigation result: {nav_result}")
        except Exception as nav_err:
            print(f"[BROWSER_TOOL] Navigation error: {nav_err}")
            import traceback
            print(f"[BROWSER_TOOL] Nav traceback:\n{traceback.format_exc()}")
            raise

        # Execute JavaScript to extract design elements
        design_script = """
        (() => {
            const result = {
                colors: [],
                fonts: [],
                components: []
            };
            const colorSet = new Set();
            const fontSet = new Set();

            const elements = document.querySelectorAll('*');
            elements.forEach(el => {
                const style = window.getComputedStyle(el);
                if (style.color) colorSet.add(style.color);
                if (style.backgroundColor && style.backgroundColor !== 'rgba(0, 0, 0, 0)') {
                    colorSet.add(style.backgroundColor);
                }
                if (style.fontFamily) {
                    const font = style.fontFamily.split(',')[0].trim().replace(/['"]/g, '');
                    fontSet.add(font);
                }
            });

            result.colors = Array.from(colorSet).slice(0, 10);
            result.fonts = Array.from(fontSet).slice(0, 5);

            if (document.querySelector('header')) result.components.push('header');
            if (document.querySelector('nav')) result.components.push('nav');
            if (document.querySelector('footer')) result.components.push('footer');
            if (document.querySelector('main')) result.components.push('main');
            if (document.querySelector('section')) result.components.push('section');
            if (document.querySelector('aside')) result.components.push('sidebar');

            return result;
        })()
        """

        # Execute JavaScript to extract design
        print(f"[BROWSER_TOOL] Executing design extraction JavaScript...")
        try:
            eval_result = browser.browser(browser_input={
                "action": {
                    "type": "evaluate",
                    "script": design_script,
                    "session_name": session_name
                }
            })
            print(f"[BROWSER_TOOL] Design eval result: {eval_result}")
        except Exception as eval_err:
            print(f"[BROWSER_TOOL] Design eval error: {eval_err}")
            import traceback
            print(f"[BROWSER_TOOL] Eval traceback:\n{traceback.format_exc()}")
            raise

        print(f"[BROWSER_TOOL] Getting page title...")
        try:
            title_result = browser.browser(browser_input={
                "action": {
                    "type": "evaluate",
                    "script": "document.title",
                    "session_name": session_name
                }
            })
            print(f"[BROWSER_TOOL] Title result: {title_result}")
        except Exception as title_err:
            print(f"[BROWSER_TOOL] Title eval error: {title_err}")
            title_result = {"result": ""}

        # Parse design data from AgentCore Browser response format
        # Format: {'status': 'success', 'content': [{'text': "Evaluation result: {...}"}]}
        design_data = {}
        try:
            if eval_result.get("status") == "success" and eval_result.get("content"):
                text_content = eval_result["content"][0].get("text", "")
                # Remove "Evaluation result: " prefix if present
                if text_content.startswith("Evaluation result: "):
                    text_content = text_content[len("Evaluation result: "):]
                # Parse the dict string
                import ast
                design_data = ast.literal_eval(text_content)
                print(f"[BROWSER_TOOL] Parsed design_data: {design_data}")
        except Exception as parse_err:
            print(f"[BROWSER_TOOL] Error parsing design data: {parse_err}")
            design_data = {}

        # Parse title from response
        title = ""
        try:
            if title_result.get("status") == "success" and title_result.get("content"):
                title_text = title_result["content"][0].get("text", "")
                if title_text.startswith("Evaluation result: "):
                    title = title_text[len("Evaluation result: "):]
                else:
                    title = title_text
                print(f"[BROWSER_TOOL] Parsed title: {title}")
        except Exception as title_parse_err:
            print(f"[BROWSER_TOOL] Error parsing title: {title_parse_err}")
            title = ""

        print(f"[BROWSER_TOOL] Final design_elements: colors={len(design_data.get('colors', []))}, fonts={len(design_data.get('fonts', []))}, components={design_data.get('components', [])}")

        return {
            "success": True,
            "url": url,
            "title": title,
            "design_elements": {
                "colors": design_data.get("colors", []) if isinstance(design_data, dict) else [],
                "fonts": design_data.get("fonts", []) if isinstance(design_data, dict) else [],
                "components": design_data.get("components", []) if isinstance(design_data, dict) else [],
                "layout": "modern" if design_data.get("components") else "simple",
            },
        }

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[BROWSER_TOOL] Extract design error: {e}")
        print(f"[BROWSER_TOOL] Full traceback:\n{error_trace}")
        logger.error(f"Extract design error: {e}\n{error_trace}")
        return {
            "success": False,
            "error": str(e),
            "url": url,
        }


@tool
def capture_page_screenshot(
    url: str,
    full_page: bool = False,
    session_name: str = "ugc-screenshot-session"
) -> dict:
    """
    Take a screenshot of a web page.

    Args:
        url: The URL to capture
        full_page: Whether to capture the full page or just viewport
        session_name: Browser session name for AgentCore

    Returns:
        dict containing:
            - success: Whether screenshot was captured
            - screenshot: Screenshot data (base64)
            - title: Page title
    """
    try:
        browser, _ = get_browser()

        # Initialize session and navigate
        browser.browser(browser_input={
            "action": {
                "type": "init_session",
                "session_name": session_name,
                "description": "Screenshot session"
            }
        })
        browser.browser(browser_input={
            "action": {
                "type": "navigate",
                "url": url,
                "session_name": session_name
            }
        })

        # Screenshot
        screenshot_result = browser.browser(browser_input={
            "action": {
                "type": "screenshot",
                "full_page": full_page,
                "session_name": session_name
            }
        })

        # Title
        title_result = browser.browser(browser_input={
            "action": {
                "type": "evaluate",
                "script": "document.title",
                "session_name": session_name
            }
        })

        return {
            "success": True,
            "url": url,
            "title": title_result.get("result", ""),
            "screenshot": screenshot_result.get("screenshot", ""),
        }

    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return {
            "success": False,
            "error": str(e),
            "url": url,
        }


# Legacy function names for backward compatibility
browser_tool = browse_url

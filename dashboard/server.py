#!/usr/bin/env python3
"""
HeadSpace Dashboard Server
Simple HTTP server for static files and SSE proxy

Serves the dashboard HTML/CSS/JS and proxies SSE events from processing service.
"""

import sys
import logging
from pathlib import Path

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

# Colorful logging
try:
    import colorlog
    COLORLOG_AVAILABLE = True
except ImportError:
    COLORLOG_AVAILABLE = False


def setup_logging():
    """Configure logging"""
    if COLORLOG_AVAILABLE:
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logging.root.addHandler(handler)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
    
    logging.root.setLevel(logging.INFO)


def create_app(static_dir: str = None):
    """Create Flask app"""
    # Resolve static directory to absolute path
    if static_dir:
        static_path = Path(static_dir).resolve()
    else:
        static_path = Path(__file__).parent.resolve()
    
    app = Flask(__name__, static_folder=str(static_path), static_url_path='')
    CORS(app)
    
    logger = logging.getLogger('Dashboard')
    
    @app.route('/')
    def index():
        """Serve index.html"""
        return send_from_directory(app.static_folder, 'index.html')
    
    @app.route('/<path:path>')
    def serve_static(path):
        """Serve static files"""
        return send_from_directory(app.static_folder, path)
    
    @app.route('/health')
    def health():
        """Health check"""
        return jsonify({'status': 'ok', 'service': 'headspace-dashboard'})
    
    logger.info(f"Dashboard serving files from: {static_path}")
    
    return app


def main():
    """Main entry point"""
    setup_logging()
    logger = logging.getLogger('Dashboard')
    
    # Determine static directory - if arg provided use it, otherwise use script's parent dir
    static_dir = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Determine port
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    else:
        port = 8080
    
    logger.info("=" * 60)
    logger.info("HeadSpace Dashboard Server")
    logger.info("=" * 60)
    
    app = create_app(static_dir)
    
    logger.info(f"Dashboard available at http://localhost:{port}")
    logger.info("Press Ctrl+C to stop")
    
    # Disable Flask request logging
    import logging as flask_logging
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.WARNING)
    
    try:
        app.run(host='0.0.0.0', port=port, threaded=True)
    except KeyboardInterrupt:
        logger.info("\nDashboard server stopped")


if __name__ == '__main__':
    main()

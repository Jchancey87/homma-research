from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from database import init_db, get_db_status


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # CORS — allow Next.js dev server and NPM proxy
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Apply schema on startup (idempotent)
    init_db()

    # Register route blueprints
    from routes.gainers       import gainers_bp
    from routes.charts        import charts_bp
    from routes.analysis      import analysis_bp
    from routes.watchlist     import watchlist_bp
    from routes.observations  import observations_bp

    app.register_blueprint(gainers_bp,      url_prefix='/api')
    app.register_blueprint(charts_bp,       url_prefix='/api')
    app.register_blueprint(analysis_bp,     url_prefix='/api')
    app.register_blueprint(watchlist_bp,    url_prefix='/api')
    app.register_blueprint(observations_bp, url_prefix='/api')

    # Start background job watchdog (resets stale 'running' jobs)
    from jobs.job_watchdog import start_watchdog
    start_watchdog()

    @app.route('/api/health')
    def health():
        return jsonify({
            'status':          'ok',
            'db_reachable':    get_db_status(),
            'llm_provider':    'groq',
            'llm_model':       Config.LLM_MODEL,
            'llm_key_set':     bool(Config.LLM_API_KEY),
        })

    # Serve chart images from the storage directory
    import os
    from flask import send_from_directory

    @app.route('/storage/charts/<path:filename>')
    def serve_chart(filename):
        return send_from_directory(
            os.path.normpath(Config.STORAGE_PATH), filename
        )

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

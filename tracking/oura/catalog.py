"""Collection registry adapted from proscar87/oura-mcp, MIT Oscar Pacheco.
Pinned revision 30b20cb5a5cd93ee34635af640db2f6ff62a4ee6. See PROSCAR_LICENSE.txt.
Names and parameter shapes checked against official Oura OpenAPI 1.43.
Scope assumptions, caching, credentials and transforms are deliberately excluded.
"""

COLLECTIONS: dict[str, tuple[str, str]] = {
    # Daily summaries: what gets queried day to day.
    "daily_sleep":              ("date_range", "sleep score and its contributors"),
    "daily_readiness":          ("date_range", "readiness score and its contributors"),
    "daily_activity":           ("date_range", "steps, calories, time by intensity"),
    "daily_stress":             ("date_range", "stress and recovery durations as reported"),
    "daily_spo2":               ("date_range", "average overnight oxygen saturation"),
    "daily_resilience":         ("date_range", "resilience (limited…exceptional)"),
    "daily_cardiovascular_age": ("date_range", "estimated cardiovascular age"),
    "vO2_max":                  ("date_range", "estimated VO2 max"),

    # The detail the scores hide.
    "sleep":        ("date_range", "sleep sessions: stages, HRV, temperature, latency"),
    "sleep_time":   ("date_range", "recommended sleep window"),
    "workout":      ("date_range", "workouts with type, duration and intensity"),
    "session":      ("date_range", "breathing, meditation and nap sessions"),
    "rest_mode_period": ("date_range", "rest mode periods"),
    "tag":          ("date_range", "tags (deprecated: Oura recommends enhanced_tag)"),
    "enhanced_tag": ("date_range", "tags with start and end times"),

    # High resolution. The only ones that FORCE pagination.
    "heartrate":          ("datetime_range", "heart rate every 5 min"),
    "ring_battery_level": ("datetime_range", "ring battery"),

    # No range.
    "personal_info":      ("single", "age, weight, height, biological sex"),
    "ring_configuration": ("token_only", "ring model, size and color"),
}

SCOPES = ('email', 'personal', 'daily', 'heartrate', 'workout', 'tag', 'session', 'spo2', 'heart_health')
API_BASE = 'https://api.ouraring.com/v2/usercollection/'
AUTHORIZE_URL = 'https://cloud.ouraring.com/oauth/authorize'
TOKEN_URL = 'https://api.ouraring.com/oauth/token'
CALLBACK_PATH = '/integrations/oura/callback/'

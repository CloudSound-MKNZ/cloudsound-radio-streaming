"""Prometheus metrics for radio streaming service."""
from prometheus_client import Counter, Histogram, Gauge
from cloudsound_shared.metrics import (
    http_requests_total,
    http_request_duration_seconds,
    playback_events_total,
    kafka_messages_produced
)

# Radio streaming specific metrics
radio_stations_total = Gauge(
    'radio_stations_total',
    'Total number of radio stations',
    ['type', 'genre']
)

radio_tracks_total = Gauge(
    'radio_tracks_total',
    'Total number of tracks',
    ['artist_id']
)

streaming_connections_active = Gauge(
    'streaming_connections_active',
    'Number of active streaming connections',
    ['station_id']
)

streaming_bytes_sent_total = Counter(
    'streaming_bytes_sent_total',
    'Total bytes sent for streaming',
    ['station_id', 'track_id']
)

playback_started_total = Counter(
    'playback_started_total',
    'Total number of playback sessions started',
    ['station_id', 'track_id']
)

playback_completed_total = Counter(
    'playback_completed_total',
    'Total number of playback sessions completed',
    ['station_id', 'track_id']
)

# Search metrics
search_queries_total = Counter(
    'search_queries_total',
    'Total number of search queries',
    ['query_type']  # 'combined', 'artists', 'tracks'
)

search_results_total = Counter(
    'search_results_total',
    'Total number of search results returned',
    ['result_type']  # 'artists', 'tracks'
)

search_duration_seconds = Histogram(
    'search_duration_seconds',
    'Time spent processing search queries',
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)
)


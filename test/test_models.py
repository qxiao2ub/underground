"""Data model tests."""
import datetime
import os
from unittest import mock

import pytest
import pytz

from underground import SubwayFeed, metadata, models
from underground.dateutils import DEFAULT_TIMEZONE
from underground.feed import load_protobuf

from . import DATA_DIR, TEST_PROTOBUFS


def test_unix_timestamp():
    """Test that datetimes are handled correctly."""
    unix_ts = models.UnixTimestamp(time=0)
    epoch_time = datetime.datetime(1970, 1, 1, 0, 0, 0, 0, pytz.timezone("UTC"))
    assert unix_ts.time == epoch_time
    assert unix_ts.timestamp_nyc == epoch_time.astimezone(
        pytz.timezone(DEFAULT_TIMEZONE)
    )


def test_header_nyc_time():
    """Test the nyc time transform for feed header."""
    header = models.FeedHeader(gtfs_realtime_version="1", timestamp=0)
    assert header.timestamp_nyc.minute == 0


def test_trip_invalid_date():
    """Test valuerror for invalid dates."""
    feed_id = next(iter(metadata.VALID_FEED_IDS))
    with pytest.raises(ValueError):
        models.Trip(trip_id="1", start_time="00:00", start_date=0, feed_id=feed_id)


def test_trip_invalid_feed():
    """Test valuerror for invalid feeds."""
    with pytest.raises(ValueError):
        models.Trip(
            trip_id="1", start_time="00:00", start_date=20190101, feed_id="FAKE"
        )


def test_extract_stop_dict():
    """Test that the correct train times are extracted."""
    sample_data = {
        "header": {"gtfs_realtime_version": "1.0", "timestamp": 0},
        "entity": [
            {
                "id": "1",
                "trip_update": {
                    "trip": {"trip_id": "X", "start_date": "20190726", "route_id": "1"},
                    "stop_time_update": [
                        {"arrival": {"time": 0}, "stop_id": "ONE"},
                        {"arrival": {"time": 1}, "stop_id": "TWO"},
                    ],
                },
            },
            {
                "id": "2",
                "trip_update": {
                    "trip": {"trip_id": "X", "start_date": "20190726", "route_id": "1"},
                    "stop_time_update": [{"arrival": {"time": 3}, "stop_id": "TWO"}],
                },
            },
        ],
    }
    stops = SubwayFeed(**sample_data).extract_stop_dict()
    assert len(stops["1"]["ONE"]) == 1
    assert len(stops["1"]["TWO"]) == 2


@pytest.mark.parametrize("filename", TEST_PROTOBUFS)
def test_on_sample_protobufs(filename):
    """Make sure the model can load up one sample from all the feeds."""
    with open(os.path.join(DATA_DIR, filename), "rb") as file:
        data = load_protobuf(file.read())

    feed = SubwayFeed(**data)
    assert isinstance(feed, SubwayFeed)
    assert isinstance(feed.extract_stop_dict(), dict)


@mock.patch("underground.feed.request")
@pytest.mark.parametrize("filename", TEST_PROTOBUFS)
def test_get(feed_request, filename):
    """Test the get method creates the desired object."""
    with open(os.path.join(DATA_DIR, filename), "rb") as file:
        feed_request.return_value = file.read()

    feed = SubwayFeed.get(16)
    assert isinstance(feed, SubwayFeed)
    assert isinstance(feed.extract_stop_dict(), dict)


def test_trip_route_remap():
    """Test that the remapping works for a known route."""
    trip = models.Trip(
        trip_id="FAKE", start_time="01:00:00", start_date=20190101, route_id="5X"
    )
    assert trip.route_id_mapped == "5"


def test_extract_dict_route_remap():
    """Test that the route remap is active for dict extraction."""
    sample_data = {
        "header": {"gtfs_realtime_version": "1.0", "timestamp": 0},
        "entity": [
            {
                "id": "X",
                "trip_update": {
                    "trip": {
                        "trip_id": "X",
                        "start_date": "20190726",
                        "route_id": "5X",
                    },
                    "stop_time_update": [{"arrival": {"time": 0}, "stop_id": "X"}],
                },
            }
        ],
    }
    stops = SubwayFeed(**sample_data).extract_stop_dict()
    assert len(stops["5"]["X"]) == 1


def test_extract_dict_elapsed_ignored():
    """Test that elapsed stops are ignored for stop extraction."""
    sample_data = {
        "header": {"gtfs_realtime_version": "1.0", "timestamp": 1},
        "entity": [
            {
                "id": "X",
                "trip_update": {
                    "trip": {"trip_id": "X", "start_date": "20190726", "route_id": "1"},
                    "stop_time_update": [
                        {"arrival": {"time": 0}, "stop_id": "IGNORED"},
                        {"arrival": {"time": 1}, "stop_id": "EXISTS"},
                    ],
                },
            }
        ],
    }

    stops = SubwayFeed(**sample_data).extract_stop_dict()
    assert "IGNORED" not in stops["1"]
    assert "EXISTS" in stops["1"]

#!/usr/bin/env python3
"""Integration test: Trigger system with API endpoints."""

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from run_agent_api import app


def test_trigger_api():
    """Test trigger API endpoints."""
    client = TestClient(app)

    print("=" * 70)
    print("TRIGGER SYSTEM API INTEGRATION TEST")
    print("=" * 70)

    # Test 1: Health check
    print("\n1. Health Check")
    response = client.get("/api/agent/health")
    assert response.status_code == 200
    data = response.json()
    print(f"   Status: {response.status_code}")
    print(f"   Groq configured: {data.get('groq_configured')}")
    print("   [PASS]")

    # Test 2: List alerts (empty)
    print("\n2. List Alerts (initial)")
    response = client.get("/api/triggers/alerts")
    assert response.status_code == 200
    data = response.json()
    print(f"   Status: {response.status_code}")
    print(f"   Alerts found: {data['count']}")
    print("   [PASS]")

    # Test 3: Run portfolio checks
    print("\n3. Run Portfolio Checks")
    response = client.post("/api/triggers/check?auto_analyze=false")
    assert response.status_code == 200
    data = response.json()
    print(f"   Status: {response.status_code}")
    print(f"   Checks run: {data['checks_run']}")
    print(f"   Detections found: {data['detections_found']}")
    print(f"   Alerts created: {data['alerts_created']}")
    print(f"   Portfolio positions: {data['portfolio_status']['positions']}")
    print("   [PASS]")

    # Test 4: Create an alert manually
    print("\n4. Create Alert (via detector simulation)")
    # Trigger checks should have created alerts if portfolio has positions
    # Now test the retrieval
    response = client.get("/api/triggers/alerts")
    assert response.status_code == 200
    data = response.json()
    total_alerts = data['count']
    print(f"   Total alerts in system: {total_alerts}")

    if total_alerts > 0:
        # Test 5: Get specific alert
        print("\n5. Get Specific Alert")
        alerts = data['alerts']
        first_alert = alerts[0]
        alert_id = first_alert['id']

        response = client.get(f"/api/triggers/alerts/{alert_id}")
        assert response.status_code == 200
        alert = response.json()
        print(f"   Alert ID: {alert_id[:12]}...")
        print(f"   Type: {alert['alert_type']}")
        print(f"   Severity: {alert['severity']}")
        print(f"   Status: {alert['status']}")
        print("   [PASS]")

        # Test 6: Analyze alert (if Groq is configured)
        print("\n6. Analyze Alert with LLM")
        from src import settings
        settings.load_settings()

        if not settings.groq_api_key():
            print("   Groq not configured - skipping LLM analysis")
        else:
            response = client.post(f"/api/triggers/alerts/{alert_id}/analyze")
            if response.status_code == 200:
                data = response.json()
                print(f"   Analysis status: {data['status']}")
                if data.get('analysis'):
                    print(f"   Alert type: {data['analysis'].get('alert_type')}")
                print("   [PASS]")
            else:
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text[:100]}")

        # Test 7: Mark alert as reviewed
        print("\n7. Mark Alert as Reviewed")
        response = client.post(
            f"/api/triggers/alerts/{alert_id}/review",
            json={"action_taken": "Reduced position size by 25%"}
        )
        assert response.status_code == 200
        alert = response.json()
        print(f"   Status: {alert['status']}")
        print(f"   Action: {alert.get('action_taken')}")
        print("   [PASS]")

        # Test 8: Filter alerts by status
        print("\n8. Filter Alerts by Status")
        response = client.get("/api/triggers/alerts?status=reviewed")
        assert response.status_code == 200
        data = response.json()
        reviewed_count = data['count']
        print(f"   Reviewed alerts: {reviewed_count}")
        print("   [PASS]")

    # Test 9: Analyze pending alerts (batch)
    print("\n9. Batch Analyze Pending Alerts")
    response = client.post("/api/triggers/analyze-pending?limit=5")
    assert response.status_code == 200
    data = response.json()
    print(f"   Analyses run: {data['analyses_run']}")
    print("   [PASS]")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)

    return True


if __name__ == "__main__":
    try:
        test_trigger_api()
        print("\nIntegration test successful!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nAssertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

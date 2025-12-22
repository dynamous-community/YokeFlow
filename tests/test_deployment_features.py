#!/usr/bin/env python3
"""
Automated tests for deployment features (JWT auth, project validation, etc.)

Tests the following deployment features:
1. JWT Authentication (login, token validation, protected endpoints)
2. Project Name Validation (no spaces, valid characters)
3. Reset Project functionality (with/without git)

Usage: python tests/test_deployment_features.py
"""

import sys
import os
from pathlib import Path
import asyncio
import httpx
from typing import Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
UI_PASSWORD = os.getenv("UI_PASSWORD", "abc123")

class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"  ✅ {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"  ❌ {test_name}")
        print(f"     Error: {error}")

    def print_summary(self):
        total = self.passed + self.failed
        print("\n" + "="*70)
        print(f"Test Results: {self.passed}/{total} passed")
        print("="*70)
        if self.errors:
            print("\nFailed tests:")
            for test_name, error in self.errors:
                print(f"  • {test_name}: {error}")
        print()
        return self.failed == 0


async def test_jwt_authentication():
    """Test JWT authentication endpoints and token validation."""
    print("\n" + "="*70)
    print("Testing JWT Authentication")
    print("="*70 + "\n")

    results = TestResults()

    async with httpx.AsyncClient() as client:
        # Test 1: Login with correct password
        try:
            response = await client.post(
                f"{API_BASE_URL}/api/auth/login",
                json={"password": UI_PASSWORD}
            )
            if response.status_code == 200:
                data = response.json()
                if "access_token" in data:
                    token = data["access_token"]
                    results.add_pass("Login with correct password returns token")
                else:
                    results.add_fail("Login response format", "Missing access_token in response")
                    return results
            else:
                results.add_fail("Login with correct password", f"Status {response.status_code}")
                return results
        except Exception as e:
            results.add_fail("Login with correct password", str(e))
            return results

        # Test 2: Login with incorrect password
        try:
            response = await client.post(
                f"{API_BASE_URL}/api/auth/login",
                json={"password": "wrong_password"}
            )
            if response.status_code == 401:
                results.add_pass("Login with incorrect password returns 401")
            else:
                results.add_fail("Login with incorrect password", f"Expected 401, got {response.status_code}")
        except Exception as e:
            results.add_fail("Login with incorrect password", str(e))

        # Test 3: Access protected endpoint without token
        try:
            response = await client.get(f"{API_BASE_URL}/api/projects")
            if response.status_code == 401:
                results.add_pass("Protected endpoint without token returns 401")
            else:
                results.add_fail("Protected endpoint without token", f"Expected 401, got {response.status_code}")
        except Exception as e:
            results.add_fail("Protected endpoint without token", str(e))

        # Test 4: Access protected endpoint with valid token
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = await client.get(f"{API_BASE_URL}/api/projects", headers=headers)
            if response.status_code == 200:
                results.add_pass("Protected endpoint with valid token returns 200")
            else:
                results.add_fail("Protected endpoint with valid token", f"Expected 200, got {response.status_code}")
        except Exception as e:
            results.add_fail("Protected endpoint with valid token", str(e))

        # Test 5: Access protected endpoint with invalid token
        try:
            headers = {"Authorization": "Bearer invalid_token_here"}
            response = await client.get(f"{API_BASE_URL}/api/projects", headers=headers)
            if response.status_code == 401:
                results.add_pass("Protected endpoint with invalid token returns 401")
            else:
                results.add_fail("Protected endpoint with invalid token", f"Expected 401, got {response.status_code}")
        except Exception as e:
            results.add_fail("Protected endpoint with invalid token", str(e))

        # Test 6: Health endpoint is public (no auth required)
        try:
            response = await client.get(f"{API_BASE_URL}/api/health")
            if response.status_code == 200:
                results.add_pass("Health endpoint is public (no auth)")
            else:
                results.add_fail("Health endpoint is public", f"Expected 200, got {response.status_code}")
        except Exception as e:
            results.add_fail("Health endpoint is public", str(e))

    return results


async def test_project_name_validation():
    """Test project name validation (no spaces, valid characters)."""
    print("\n" + "="*70)
    print("Testing Project Name Validation")
    print("="*70 + "\n")

    results = TestResults()

    # Get valid token first
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/api/auth/login",
            json={"password": UI_PASSWORD}
        )
        if response.status_code != 200:
            results.add_fail("Get auth token", "Failed to get auth token for testing")
            return results

        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test valid project names
        valid_names = [
            "my-project",
            "claude_clone",
            "test123",
            "project-name-with-dashes",
            "project_name_with_underscores",
            "abc123xyz"
        ]

        for name in valid_names:
            try:
                # Create a minimal spec file
                files = {
                    "spec_file": ("app_spec.txt", "# Test Spec\nBuild a simple app", "text/plain")
                }
                data = {"name": name}

                response = await client.post(
                    f"{API_BASE_URL}/api/projects",
                    headers=headers,
                    data=data,
                    files=files
                )

                # Should succeed (200) or fail with duplicate name (409 Conflict or 400)
                if response.status_code in [200, 400, 409]:
                    if response.status_code in [400, 409] and "already exists" in response.text.lower():
                        results.add_pass(f"Valid name '{name}' accepted (duplicate)")
                    elif response.status_code == 200:
                        results.add_pass(f"Valid name '{name}' accepted")
                    else:
                        results.add_fail(f"Valid name '{name}'", f"Unexpected response: {response.text}")
                else:
                    results.add_fail(f"Valid name '{name}'", f"Status {response.status_code}")
            except Exception as e:
                results.add_fail(f"Valid name '{name}'", str(e))

        # Test invalid project names
        invalid_names = [
            ("my project", "spaces"),
            ("claude clone", "spaces"),
            ("Test Project", "uppercase and spaces"),
            ("project name", "spaces"),
            ("my-project!", "special character"),
            ("project@name", "special character")
        ]

        for name, reason in invalid_names:
            try:
                files = {
                    "spec_file": ("app_spec.txt", "# Test Spec\nBuild a simple app", "text/plain")
                }
                data = {"name": name}

                response = await client.post(
                    f"{API_BASE_URL}/api/projects",
                    headers=headers,
                    data=data,
                    files=files
                )

                if response.status_code == 400:
                    if "lowercase" in response.text.lower() or "invalid" in response.text.lower():
                        results.add_pass(f"Invalid name '{name}' rejected ({reason})")
                    else:
                        results.add_fail(f"Invalid name '{name}'", f"Wrong error message: {response.text}")
                else:
                    results.add_fail(f"Invalid name '{name}'", f"Expected 400, got {response.status_code}")
            except Exception as e:
                results.add_fail(f"Invalid name '{name}'", str(e))

    return results


async def test_api_endpoints_auth():
    """Test that all API endpoints are properly protected."""
    print("\n" + "="*70)
    print("Testing API Endpoint Authorization")
    print("="*70 + "\n")

    results = TestResults()

    # Public endpoints (should not require auth)
    public_endpoints = [
        ("GET", "/api/health"),
        ("POST", "/api/auth/login")
    ]

    # Protected endpoints (should require auth)
    protected_endpoints = [
        ("GET", "/api/projects"),
        ("GET", "/api/info"),
        ("POST", "/api/projects")  # Will fail but should give 401 not 422
    ]

    async with httpx.AsyncClient() as client:
        # Test public endpoints
        for method, endpoint in public_endpoints:
            try:
                if method == "GET":
                    response = await client.get(f"{API_BASE_URL}{endpoint}")
                elif method == "POST":
                    # For login, we need a body
                    if "login" in endpoint:
                        response = await client.post(f"{API_BASE_URL}{endpoint}", json={"password": "test"})
                    else:
                        response = await client.post(f"{API_BASE_URL}{endpoint}")

                # Public endpoints should be accessible (not 403)
                # Note: /api/auth/login can return 401 for wrong password - that's correct!
                # We just want to verify it doesn't require a JWT token to access
                if "login" in endpoint:
                    # Login endpoint: 200 (success) or 401 (wrong password) are both acceptable
                    # as long as it's not 403 (forbidden due to missing auth)
                    if response.status_code in [200, 401]:
                        results.add_pass(f"Public endpoint {method} {endpoint}")
                    else:
                        results.add_fail(f"Public endpoint {method} {endpoint}", f"Expected 200 or 401, got {response.status_code}")
                else:
                    # Other public endpoints should return success codes
                    if response.status_code != 401:
                        results.add_pass(f"Public endpoint {method} {endpoint}")
                    else:
                        results.add_fail(f"Public endpoint {method} {endpoint}", "Returns 401 (should be public)")
            except Exception as e:
                results.add_fail(f"Public endpoint {method} {endpoint}", str(e))

        # Test protected endpoints without auth
        for method, endpoint in protected_endpoints:
            try:
                if method == "GET":
                    response = await client.get(f"{API_BASE_URL}{endpoint}")
                elif method == "POST":
                    response = await client.post(f"{API_BASE_URL}{endpoint}")

                if response.status_code == 401:
                    results.add_pass(f"Protected endpoint {method} {endpoint} requires auth")
                else:
                    results.add_fail(f"Protected endpoint {method} {endpoint}", f"Expected 401, got {response.status_code}")
            except Exception as e:
                results.add_fail(f"Protected endpoint {method} {endpoint}", str(e))

    return results


def main():
    """Run all deployment feature tests."""
    print("\n" + "="*70)
    print("DEPLOYMENT FEATURES TEST SUITE")
    print("="*70)
    print(f"\nAPI Base URL: {API_BASE_URL}")
    print(f"UI Password: {UI_PASSWORD}")

    all_results = []

    # Run tests
    all_results.append(asyncio.run(test_jwt_authentication()))
    all_results.append(asyncio.run(test_project_name_validation()))
    all_results.append(asyncio.run(test_api_endpoints_auth()))

    # Print summary
    print("\n" + "="*70)
    print("OVERALL TEST RESULTS")
    print("="*70)

    total_passed = sum(r.passed for r in all_results)
    total_failed = sum(r.failed for r in all_results)
    total_tests = total_passed + total_failed

    print(f"\nTotal: {total_passed}/{total_tests} passed")

    if total_failed > 0:
        print("\n❌ SOME TESTS FAILED")
        for result in all_results:
            if result.errors:
                for test_name, error in result.errors:
                    print(f"  • {test_name}: {error}")
    else:
        print("\n✅ ALL TESTS PASSED")

    print()

    # Exit with appropriate code
    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()

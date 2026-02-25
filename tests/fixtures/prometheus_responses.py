"""Mock Prometheus API responses for testing"""

# Sample Prometheus response with 50% usage (5 GB used / 10 GB quota)
PROMETHEUS_QUOTA_50_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314029.985, "10737418240"],  # 10 GB
            },
        ],
    },
}

PROMETHEUS_USAGE_50_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314216.003, "5368709120"],  # 5 GB
            },
        ],
    },
}

PROMETHEUS_TIMESTAMP_50_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314216.003, "1771314216.003"],
            },
        ],
    },
}

# Sample Prometheus response with 90% usage (threshold for warning)
PROMETHEUS_QUOTA_90_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314029.985, "10737418240"],  # 10 GB
            },
        ],
    },
}

PROMETHEUS_USAGE_90_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314216.003, "9663676416"],  # 9 GB (90%)
            },
        ],
    },
}

# Sample Prometheus response with 95% usage (high warning)
PROMETHEUS_QUOTA_95_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314029.985, "10737418240"],  # 10 GB
            },
        ],
    },
}

PROMETHEUS_USAGE_95_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314216.003, "10200547328"],  # 9.5 GB (95%)
            },
        ],
    },
}

# 0% usage
PROMETHEUS_QUOTA_0_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314029.985, "10737418240"],  # 10 GB
            },
        ],
    },
}

PROMETHEUS_USAGE_0_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314216.003, "0"],  # 0 bytes
            },
        ],
    },
}

# 100% usage
PROMETHEUS_QUOTA_100_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314029.985, "10737418240"],  # 10 GB
            },
        ],
    },
}

PROMETHEUS_USAGE_100_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314216.003, "10737418240"],  # 10 GB (100%)
            },
        ],
    },
}

# Empty results (no data for user)
PROMETHEUS_EMPTY_RESULT = {
    "status": "success",
    "data": {"resultType": "vector", "result": []},
}

# Prometheus error response
PROMETHEUS_ERROR_RESPONSE = {
    "status": "error",
    "error": "query timeout",
    "errorType": "timeout",
}

# Malformed responses
PROMETHEUS_MALFORMED_NO_DATA = {
    "status": "success",
    # missing 'data' field
}

PROMETHEUS_MALFORMED_NO_RESULT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        # missing 'result' field
    },
}

PROMETHEUS_MALFORMED_INVALID_VALUE = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                },
                "value": [1771314029.985],  # Missing second element
            },
        ],
    },
}

PROMETHEUS_MALFORMED_NON_NUMERIC = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                },
                "value": [1771314029.985, "not-a-number"],
            },
        ],
    },
}

# Multiple namespaces in response
PROMETHEUS_MULTIPLE_NAMESPACES_QUOTA = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314029.985, "10737418240"],  # 10 GB
            },
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "staging",
                    "username": "testuser",
                },
                "value": [1771314029.985, "5368709120"],  # 5 GB
            },
        ],
    },
}

PROMETHEUS_MULTIPLE_NAMESPACES_USAGE = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314216.003, "5368709120"],  # 5 GB
            },
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "staging",
                    "username": "testuser",
                },
                "value": [1771314216.003, "2684354560"],  # 2.5 GB
            },
        ],
    },
}

# Very large quota (terabytes)
PROMETHEUS_QUOTA_TERABYTES = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314029.985, "1099511627776"],  # 1 TB
            },
        ],
    },
}

PROMETHEUS_USAGE_TERABYTES = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314216.003, "549755813888"],  # 512 GB
            },
        ],
    },
}

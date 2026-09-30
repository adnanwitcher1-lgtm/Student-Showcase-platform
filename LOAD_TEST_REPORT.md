# Load Test Report

**Tool:** Locust
**Simulated Users:** 50
**Spawn Rate:** 5 users/second
**Duration:** 3 Minutes

---

## Results (Before Index Optimization)

- Median Response Time: 4100 ms
- 95th Percentile: 4100 ms
- Failure Rate: 4.2%

### Endpoint Performance

| Endpoint | Avg Response Time |
|-----------|------------------|
| /api/projects/ | 296.65 ms |
| /api/projects/?search=react | 283.44 ms |
| /api/projects/my-second-project/ | 400.66 ms |
| /api/projects/my-second-project/demo-url/ | 311.60 ms |

---

## Results (After Adding Indexes on status, owner)

- Median Response Time: 410 ms
- 95th Percentile: 2100 ms
- Failure Rate: 1.7%

### Endpoint Performance

| Endpoint | Avg Response Time |
|-----------|------------------|
| /api/projects/ | 180.16 ms |
| /api/projects/?search=react | 52.48 ms |
| /api/projects/my-second-project/ | 764.56 ms |
| /api/projects/my-second-project/demo-url/ | 181.92 ms |

---

## Bottlenecks Identified

- Project detail endpoint is the slowest endpoint.
- Demo URL endpoint triggers rate limiting (HTTP 429).
- Earlier tests had ConnectionRefusedError because Django server was unavailable.
- Some requests reached high response times under load.

---

## Fixes Applied

- Added database index on Project.title
- Added database index on Project.status
- Added database index on Project.owner

```python
class Meta:
    indexes = [
        models.Index(fields=['title']),
        models.Index(fields=['status']),
        models.Index(fields=['owner']),
    ]
```

---

## Observations

- Search endpoint improved significantly.
- Project listing endpoint improved noticeably.
- Failure rate reduced from 4.2% to 1.7%.
- Database indexing helped filtering and search operations.
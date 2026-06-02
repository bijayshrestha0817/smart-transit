# Code Patterns: Concrete Examples

## Deep Module Pattern

### Bad: Shallow decomposition (12 functions to understand one flow)
```python
def validate_email(email): ...
def check_email_domain(email): ...  
def normalize_email(email): ...
def create_user_record(email, name): ...
def assign_default_role(user): ...
def send_welcome_email(user): ...
def log_registration(user): ...

def register_user(email, name):
    email = normalize_email(email)
    validate_email(email)
    check_email_domain(email)
    user = create_user_record(email, name)
    assign_default_role(user)
    send_welcome_email(user)
    log_registration(user)
    return user
```

### Good: Deep module with clear interface
```python
def register_user(email: str, name: str) -> User:
    """Register a new user. Validates, creates record, sends welcome email.
    Raises InvalidEmail or DuplicateUser."""
    email = email.strip().lower()
    if not _is_valid_email(email):
        raise InvalidEmail(email)

    user = User(email=email, name=name, role=Role.DEFAULT)
    db.save(user)
    notifications.send_welcome(user)
    logger.info("registered", user_id=user.id)
    return user
```

The second version is one function you can read top-to-bottom. The helpers (`_is_valid_email`)
are private — implementation details, not API surface. The interface is one function with obvious
inputs and outputs.

## Errors as Values

### Bad: Exception-driven control flow
```python
try:
    user = find_user(user_id)
    try:
        order = create_order(user, items)
        try:
            charge = process_payment(order)
        except PaymentError as e:
            cancel_order(order)
            raise
    except OrderError as e:
        notify_support(e)
        raise
except UserNotFound:
    return error_response(404, "User not found")
except PaymentError as e:
    return error_response(402, str(e))
except OrderError as e:
    return error_response(400, str(e))
```

### Good: Errors as data with explicit flow
```python
def place_order(user_id: str, items: list[Item]) -> Result[Order, OrderError]:
    user = users.find(user_id)
    if not user:
        return Err(OrderError.user_not_found(user_id))

    order = Order.create(user, items)
    if not order.is_valid():
        return Err(OrderError.invalid_order(order.validation_errors))

    payment = payments.charge(order)
    if not payment.succeeded:
        return Err(OrderError.payment_failed(payment.reason))

    order.confirm(payment)
    db.save(order)
    return Ok(order)
```

Linear flow. Every failure case is visible. No hidden control flow jumps.

## Honest Boundary Test

### Bad: Boundary in the wrong place (too many params crossing)
```python
class UserService:
    def create_user(self, email, name, role, department, manager_id,
                    permissions, notification_prefs, locale, timezone):
        ...

class UserController:
    def handle_registration(self, request):
        self.user_service.create_user(
            request.email, request.name, request.role,
            request.department, request.manager_id,
            request.permissions, request.notification_prefs,
            request.locale, request.timezone
        )
```

### Good: Boundary reflects domain concept
```python
@dataclass
class NewUserRequest:
    email: str
    name: str
    role: Role
    department: str
    manager_id: str | None = None

class UserService:
    def register(self, request: NewUserRequest) -> User:
        ...
```

If a boundary requires passing many parameters, either the boundary is wrong or the data
should be grouped into a domain concept.

## Behavioral Testing

### Bad: Tests coupled to implementation
```python
def test_user_registration():
    mock_db = Mock()
    mock_emailer = Mock()
    service = UserService(db=mock_db, emailer=mock_emailer)

    service.register("test@example.com", "Test User")

    mock_db.save.assert_called_once()
    mock_emailer.send.assert_called_once_with(
        to="test@example.com",
        template="welcome",
        subject="Welcome!"
    )
```

### Good: Tests verify behavior
```python
def test_registered_user_can_log_in():
    app = create_test_app()
    app.register_user("test@example.com", "Test User")

    result = app.login("test@example.com")

    assert result.success
    assert result.user.name == "Test User"

def test_registration_sends_welcome_email():
    app = create_test_app()
    app.register_user("test@example.com", "Test User")

    assert app.outbox.has_email_to("test@example.com")
    assert "welcome" in app.outbox.last_email.subject.lower()
```

The first test breaks when you rename a method or change email templates. The second test
breaks only when behavior changes.

## Naming Precision

### Vague (signals unclear thinking)
```
handle_data()
process_items()
manage_state()
UserManager
DataHelper
ServiceUtils
do_stuff()
run()
```

### Precise (reveals intent)
```
parse_icd_codes_from_chart()
calculate_risk_adjustment_score()
route_claim_to_adjudicator()
ClaimAdjudicator
ChartParser
RiskScoreCalculator
submit_prior_authorization()
extract_diagnosis_from_note()
```

## Configuration Minimalism

### Bad: Everything configurable
```yaml
app:
  max_retries: 3
  retry_delay_ms: 1000
  retry_backoff_factor: 2.0
  connection_timeout_ms: 5000
  read_timeout_ms: 30000
  max_connections: 100
  min_connections: 10
  idle_timeout_ms: 60000
  log_level: INFO
  log_format: json
  log_file: /var/log/app.log
  enable_metrics: true
  metrics_port: 9090
  metrics_path: /metrics
  # ... 50 more options
```

### Good: Strong defaults, minimal surface
```python
# config.py — only what varies between environments
@dataclass
class Config:
    database_url: str          # Always different per environment
    api_key: str               # Secret, must be injected
    environment: str = "prod"  # Affects logging verbosity

    # Everything else has a sensible default that rarely changes.
    # If you need to tune connection pools, do it in code with a comment
    # explaining why the default was insufficient.
```

## Dependency Isolation

### When to wrap (volatile/risky dependency)
```python
# payment_gateway.py — our interface
class PaymentGateway(Protocol):
    def charge(self, amount: Money, source: PaymentSource) -> ChargeResult: ...

# stripe_gateway.py — adapter to volatile external dependency
class StripeGateway:
    def charge(self, amount: Money, source: PaymentSource) -> ChargeResult:
        stripe_result = stripe.Charge.create(...)
        return ChargeResult.from_stripe(stripe_result)
```

### When NOT to wrap (stable, deeply integrated)
```python
# Don't wrap SQLAlchemy, React, or other foundational dependencies.
# If you're replacing your ORM, you're rewriting the app anyway.
from sqlalchemy import Column, Integer, String
```

**Rule of thumb**: Wrap at the level where substitution is realistic. If swapping the dependency
would require rewriting 30% of the app, wrapping is theater.

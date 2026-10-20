FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

COPY docker/requirements-test.txt /opt/requirements-test.txt
RUN pip install --no-cache-dir -r /opt/requirements-test.txt \
    && groupadd --gid 10001 runner \
    && useradd --uid 10001 --gid 10001 --no-create-home runner \
    && mkdir /candidate

COPY docker/pytest.ini /tests/pytest.ini
COPY tests/candidates/ /tests/

USER 10001:10001
WORKDIR /tmp

ENTRYPOINT ["python", "-m", "pytest"]
CMD ["/tests/test_sql_delete_user.py", "-v", "-p", "no:cacheprovider", "--basetemp=/tmp/pytest"]

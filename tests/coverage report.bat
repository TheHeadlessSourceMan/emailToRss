coverage run --omit=test.py test.py
coverage html -d htmlcov
@rem firefox .\htmlcov\index.html
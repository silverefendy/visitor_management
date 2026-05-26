from setuptools import find_packages, setup

with open("requirements.txt") as f:
    install_requires = [
        line.strip()
        for line in f.read().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

setup(
    name="visitor_management",
    version="1.0.0",
    description="Visitor Management System for ERPNext",
    author="FnD Corp",
    author_email="silver_efendy@yahoo.co.id",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)

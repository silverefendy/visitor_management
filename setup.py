from setuptools import find_packages, setup

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

setup(
	name="visitor_management",
	version="1.0.0",
	description="Visitor Management System for ERPNext",
	author="Your Company",
	author_email="admin@yourcompany.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires,
)

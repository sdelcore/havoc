from setuptools import find_packages, setup

package_name = 'havoc_policies'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', ['config/twist_mux.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Spencer Delcore',
    maintainer_email='sdelcore@gmail.com',
    description='Driving policy abstractions for Havoc.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # Each policy is its own executable. The autonomous.launch.py
            # file in havoc_bringup picks one via a launch arg.
            'constant = havoc_policies.constant:main',
        ],
    },
)

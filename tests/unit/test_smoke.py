def test_package_imports():
    import packer
    import packer.engine
    import packer.engine.common

    assert packer.__name__ == "packer"

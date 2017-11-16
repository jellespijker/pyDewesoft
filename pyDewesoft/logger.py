import logging
import logging.config
import os
import yaml

__all__ = ['setup_logging', 'logged']


def setup_logging(default_path: str = 'logging.yaml', default_level: int = logging.INFO, env_key: str = 'LOG_CFG'):
    r"""
    Setups a logging configuration

    Args:
        :param default_path: Path to the yaml file containg the configuration
        :type default_path: str

        :param default_level: default logging level of configuration when logging configuration couldn't be found
        :type default_level: int

        :param env_key: The ENVIRONMENT VARIABLE with the path tot the logging file
        :type env_key: str
    """
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


def logged(obj):
    r"""
    Decorator to make sure that all loggers use the same setup

    Args:
        :param cls: The class that needs to have a logger
        :type cls: object

    Returns:
        :return: a class with a logger object
        :rtype: object
    """
    if isinstance(obj, object):
        if type(obj).__qualname__ == 'function':
            obj.logger = logging.getLogger('{}.{}'.format(obj.__module__, obj.__qualname__))
            obj.logger.__doc__ = r"The function logger"
        else:
            obj.logger = logging.getLogger('pyDewesoft')
            obj.logger.__doc__ = r"The class logger"
        return obj
    return obj

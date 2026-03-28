import io
import os


DIRNAME = os.path.dirname(os.path.abspath(__file__))


def input_filename(*parts):
    return os.path.join(DIRNAME, 'input', *parts)


def input_file(*parts, **kwargs):
    encoding = kwargs.pop('encoding', 'utf-8')
    with io.open(input_filename(*parts), 'rt', encoding=encoding) as f:
        return f.read()

import unittest
from tools.resolve_feishu_wiki import node_token, resolve, SafeError


class WikiResolverTests(unittest.TestCase):
    def test_extract_node(self):
        self.assertEqual(node_token('https://example.feishu.cn/wiki/mockNode?table=mockTable'), 'mockNode')
        self.assertEqual(node_token('mockNode'), 'mockNode')

    def test_wrong_domain_or_path_rejected(self):
        for url in ['https://example.org/wiki/mockNode', 'https://example.feishu.cn/base/mockBase']:
            with self.subTest(url=url), self.assertRaises(SafeError):
                node_token(url)

    def test_only_auth_and_node_calls(self):
        paths = []
        def call(path, **kwargs):
            paths.append(path)
            if len(paths) == 1:
                return {'tenant_access_token': 'mock-access'}
            self.assertNotIn('payload', kwargs)
            return {'data': {'node': {'obj_type': 'bitable', 'obj_token': 'mock-base', 'title': 'unused'}}}
        self.assertEqual(resolve('mock-id', 'mock-secret', 'mock-node', call), 'mock-base')
        self.assertEqual(len(paths), 2)
        self.assertTrue(paths[1].startswith('wiki/v2/spaces/get_node?'))

    def test_non_bitable_rejected(self):
        def call(path, **kwargs):
            if path.startswith('auth/'):
                return {'tenant_access_token': 'mock-access'}
            return {'data': {'node': {'obj_type': 'docx', 'obj_token': 'mock-document'}}}
        with self.assertRaises(SafeError):
            resolve('mock-id', 'mock-secret', 'mock-node', call)

    def test_missing_access_token_stops(self):
        with self.assertRaises(SafeError):
            resolve('mock-id', 'mock-secret', 'mock-node', lambda *a, **k: {})

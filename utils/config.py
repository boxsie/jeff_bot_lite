


class Config:
    def __init__(self, cfg_json, base_bucket):
        self.paths = cfg_json['path']
        self.base_bucket = base_bucket


    def get_bucket_path(self, resource_name):
        if not resource_name in self.paths:
            raise Exception(f'Cannot find the resource path for {resource_name}')

        return f'{self.base_bucket}/{self.paths[resource_name]}'
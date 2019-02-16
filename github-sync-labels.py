#! /usr/bin/env python3.6

import sys
import os
import re
import csv
import argparse
import typing

from requests import request


__version__ = '0.4.0'


"""
TODO: read from standard input
TODO: Generator properties
TODO: Export csv
"""


GITHUB_LINKS_HEADER_PATTERN = re.compile('\s?<(?P<url>.+)>; rel="(?P<tag>\w+)"')


LABELS = '''
architecture,2B2026
blocking,B60205
bug,EE0701
ci,8D8D00
deployment,656B75
documentation,FBCA04
draft,FF9600
duplicate,CCCCCC
enhancement,84B6EB
feature,C2E0C6
functionality test,FEF2C0
graphical prototype,FF4650
graphical design,7C6BD6
graphical wireframe,D50745
invalid,E6E6E6
layout,F9D0C4
pending,6519E7
question,CC317C
revise,FF04E4
rest story,E1B4C9
r&d,D4C5F9
user interface,651213
wontfix,FFFFFF
'''.lower().strip()

parser = argparse.ArgumentParser(description='A tool to update multiple organization\'s repositories labels.')
parser.add_argument(
    'organizations',
    nargs='+',
    metavar='organization[/repository]',
    help='An organization name for updating labels'
)
parser.add_argument(
    '-e', '--exclude',
    action='append',
    dest='excludes',
    default=[],
    metavar='{organization/}repository',
    help='An organization\'s repository name to be excluded from updating labels'
)
parser.add_argument(
    '-t', '--token',
    type=str,
    default=os.environ.get('GITHUB_OAUTH_TOKEN'),
    help='A github personal access token, for more info see: '
         'https://help.github.com/articles/creating-a-personal-access-token-for-the-command-line/'
)
parser.add_argument(
    '-y', '--yes',
    action='store_true',
    help='Assume yes to all prompt.'
)
parser.add_argument(
    '-f', '--file-name',
    help='A file name contains a list of comma separated label and colors.'
)
arguments = parser.parse_args()

GITHUB_REQUEST_HEADERS = {
    'Authorization': f'token {arguments.token}',
    'X-OAuth-Scopes': 'admin:repository_hook',
    'Accept': 'application/vnd.github.machine-man-preview+json'
}
GITHUB_BASE_URL = 'https://api.github.com'


def read_csv(filename):
    with open(filename) as label_files:
        reader = csv.reader(label_files, quotechar=',')
        return dict(reader)


labels = {k: v for k, v in [l.split(',') for l in LABELS.splitlines()]} if arguments.file_name is None \
    else read_csv(arguments.file_name)


class HttpError(Exception):
    pass


class AbortException(Exception):
    pass


class SkipException(Exception):
    pass


def github(verb, url, json=None):
    # TODO: timeout
    # TODO: errors
    if not url.lower().startswith('http'):
        if url.startswith('/'):
            url = url[1:]
        url = f'{GITHUB_BASE_URL}/{url}'

    print(f'Calling {verb} on {url}', end='')
    if json:
        data = [f'{k}={v}' for k, v in json.items()]
        print(f'?{"&".join(data)}')
    else:
        print()

    response = request(verb, url, headers=GITHUB_REQUEST_HEADERS, json=json)
    if response.status_code not in [200, 201, 204]:
        print(f'ERROR: Got {response.status_code} when requesting {url}')
        raise HttpError(response.status_code)

    return response


class Label:

    def __init__(self, name, color, url=None, **kwargs):
        self.name = name.strip()
        self.color = color.strip()
        self.url = url
        self.attributes = kwargs

    def log(self, entry):
        History.current.get_label_log(self).append(entry)

    @property
    def red(self):
        return int(self.color[:2], 16)

    @property
    def green(self):
        return int(self.color[2:4], 16)

    @property
    def blue(self):
        return int(self.color[4:], 16)


class GithubLabel(Label):

    def __init__(self, repository, *args, **kwargs):
        self.repository = repository
        super().__init__(*args, **kwargs)

    def delete(self):
        if not arguments.yes:
            confirmation = input(
                f'Label {self.name} with #{self.color} will be removed from {self.repository.full_name} by your '
                f'confirmation. [YES/No/Abort/Skip]: '
            ).lower()

            if confirmation == 'abort':
                raise AbortException()

            if confirmation == 'skip':
                raise SkipException()

            while confirmation == 'y':
                confirmation = input(
                    f'Please type yes to confirm and anything else to abort: '
                ).lower()

            if confirmation.lower() != 'yes':
                self.log(f'Delete canceled by user')
                return

        github('delete', self.url)
        self.log(f'Deleted')

    def ensure_casing(self):
        good_name = self.name.lower()
        if self.name == good_name:
            return False
        github('patch', self.url, json=dict(name=good_name))
        self.log(f'Renamed from {self.name} to {good_name}')
        self.name = good_name
        return True

    def rename(self):
        for name, color in labels.items():
            if color == self.color:
                new_name = name
        old_name = self.name
        self.name = new_name
        github('patch', self.url, json=dict(name=new_name))
        self.log(f'Renamed from {old_name} to {new_name}')
        return True

    def ensure_color(self):
        if self.name.lower() not in labels:
            return False
        true_color = labels[self.name.lower()]
        if self.color == true_color:
            return False
        github('patch', self.url, json=dict(color=true_color))
        self.log(f'Color is changed from #{self.color} to #{true_color}')
        self.color = true_color
        return True

    @property
    def is_garbage(self):
        return not(self.is_standard or self.is_custom)

    @property
    def is_custom(self):
        return self.red <= 100 and 40 <= self.green <= 140 and 20 <= self.blue <= 120

    @property
    def is_standard(self):
        return self.name.lower() in labels

    @property
    def is_renamed(self):
        return self.color in labels.values() and self.name.lower() not in labels


class Repository:

    def __init__(self, organization, attributes):
        self.organization = organization
        self.full_name = attributes['full_name']
        self.name = attributes['name']

    @property
    def labels(self) -> typing.Iterable[GithubLabel]:
        response = github('get', f'repos/{self.full_name}/labels')
        for labels_data in response.json():
            yield GithubLabel(repository=self, **labels_data)

    @property
    def is_excluded(self):
        return self.full_name in arguments.excludes or self.name in arguments.excludes

    def synchronize_labels(self):
        if self.is_excluded:
            print(f'{self.full_name} repository is ignored.')
            return

        with History(self) as history:
            try:
                for label in self.labels:
                    changed = False
                    if label.is_standard:
                        changed |= label.ensure_color()
                        changed |= label.ensure_casing()
                    elif label.is_custom:
                        changed |= label.ensure_casing()
                        label.log(
                            f'color will not changed because this is a custom label: '
                            f'(R: {label.red}, G: {label.green}, B: {label.blue})'
                        )
                    elif label.is_renamed:
                        changed |= label.ensure_casing()
                        changed |= label.rename()
                    else:
                        label.delete()
                        changed = True

                    if not changed:
                        label.log('was not changed')

                for label in History.current.get_remaining_labels():
                    github('post', f'repos/{self.full_name}/labels', json=dict(name=label.name, color=label.color))
                    label.log(f'created with color: #{label.color}')

            except SkipException:
                print(f'{self.full_name} repository skipped by user.')
            finally:
                print(history.report())


class Organization:
    def __init__(self, attributes):
        self.name = attributes['login']
        self.repositories_url = attributes['repos_url']

    @classmethod
    def load(cls, name=None) -> 'Organization':
        response = github('get', f'orgs/{name}')
        return cls(response.json())

    @staticmethod
    def extract_header_links(response):
        result = {}
        link_header = response.headers.get('Link')
        if not link_header:
            return result
        links = link_header.split(',')
        for link in links:
            url, tag = GITHUB_LINKS_HEADER_PATTERN.match(link).groups()
            result[tag] = url
        return result

    @property
    def repositories(self) -> typing.Iterable[Repository]:
        url = self.repositories_url
        while url is not None:
            response = github('get', url)
            for repository_data in response.json():
                yield Repository(self, repository_data)
            links = self.extract_header_links(response)
            url = links.get('next')

    @staticmethod
    def synchronize_labels(repositories):
        for repository in repositories:
            repository.synchronize_labels()

    def get_repository(self, repository_name):
        response = github('get', f'repos/{self.name}/{repository_name}')
        return Repository(self, response.json())


class History:
    current: 'History' = None

    def __init__(self, repository):
        self.repository = repository
        self.labels = {}

    def get_label_log(self, label):
        return self.labels.setdefault(label.name.lower(), [])

    def get_remaining_labels(self) -> typing.Iterable[Label]:
        return [Label(name=n, color=labels[n]) for n in set(labels) - set(self.labels)]

    def report(self):
        title = [f'{self.repository.full_name}:']
        logs = [
            f'{label.ljust(8 + max(map(len, self.labels.keys())))}{log_entry}'
            for label, logs in self.labels.items() for log_entry in logs
        ]
        return '\n'.join(title + logs)

    def __enter__(self):
        self.__class__.current = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__class__.current = None


def main():
    for organization_name in arguments.organizations:
        if '/' in organization_name:
            organization_name, repository_name = organization_name.split('/')
            organization = Organization.load(organization_name)
            repository = organization.get_repository(repository_name)
            repository.synchronize_labels()
        else:
            organization = Organization.load(organization_name)
            organization.synchronize_labels(organization.repositories)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('CTRL+C just pressed!')
        sys.exit(2)

    except AbortException:
        print('Script stopped by user.')
        sys.exit(3)

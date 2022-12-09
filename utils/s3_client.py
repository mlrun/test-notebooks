from typing import List
import os
import glob
import warnings

import boto3

# Import tqdm progressbar according to the running environment (jupyter or cli):
get_ipython_function = globals().get("get_ipython", None)
if get_ipython_function:
    shell = get_ipython_function().__class__.__name__
    if shell == "ZMQInteractiveShell":
        from tqdm.notebook import tqdm
    else:
        from tqdm import tqdm
else:
    from tqdm import tqdm


class S3Client:
    """
    An easy to use S# client for uploading, downloading and deleting single files or directories.

    S3 do not have actual directories. Each file's name is a key, but if the key has a seperator '/' in it the UI in S3
    shows it as a directory. This client handles these kind of directories.
    """

    def __init__(
        self,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
    ):
        """
        Initialize a S3 client object (not opening a session yet) with the given credentials.

        :param aws_access_key_id:     The AWS access key id.
        :param aws_secret_access_key: The AWS secret access key.
        """
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key

    def upload(
        self,
        bucket: str,
        local_path: str,
        s3_path: str,
        replace: bool = True,
        verbose: bool = True,
    ):
        """
        Upload a given file or directory to S3.

        Please notice to not put a '/' prefix in the `s3_path` as S3 will interpreate the '/' as a directory named '/'.

        :param bucket:     The bucket to upload to.
        :param local_path: The path to the local file or directory to upload.
        :param s3_path:    The path to upload to in the S3 bucket.
        :param replace:    Whether to replace the files when uploading or skip if they already exist. Default: True.
        :param verbose:    Whether to log uploading information. Default: True.

        :raise ValueError: If the given local path do not exist, or it is a path of an empty directory.

        Example:
            >>> s3_client = S3Client()
            >>> s3_client.upload(
            ...     bucket="my_bucket",
            ...     local_path="/path/to/a/local/directory",
            ...     s3_path="path/to/a/s3/directory",
            ...     replace=False,
            ... )
        """
        # Initialize a S3 client:
        s3 = self._init_client()

        # Check if the given S3 path is starting with a '/':
        if s3_path[0] == "/":
            warnings.warn(
                f"Uploading to S3 with a path starting with a '/' is not recommended. Given S3 path: '{s3_path}'. "
                f"S3 do not have directories, the UI simply parse separators ('/') in the files keys as directories. "
                f"Hence, putting a '/' at the beginning of the path will create a directory named '/'."
            )

        # Check if path exist:
        if not os.path.exists(local_path):
            raise ValueError(f"The given local path '{local_path}' do not exist")

        # Check if it's a single file or directory:
        if os.path.isfile(local_path):
            self._upload_file(
                s3_client=s3,
                local_path=local_path,
                s3_path=s3_path,
                bucket=bucket,
                replace=replace,
                verbose=verbose,
            )
        else:
            self._upload_directory(
                s3_client=s3,
                local_path=local_path,
                s3_path=s3_path,
                bucket=bucket,
                replace=replace,
                verbose=verbose,
            )
        if verbose:
            print("Done!")

    def download(
        self,
        bucket: str,
        local_path: str,
        s3_path: str,
        replace: bool = True,
        verbose: bool = True,
    ):
        """
        Download a given file or directory from S3.

        :param bucket:     The bucket to download from.
        :param local_path: The path to the local file or directory to download to.
        :param s3_path:    The path to the file or directory to download in the S3 bucket.
        :param replace:    Whether to replace the files when downloading or skip if they already exist. Default: True.
        :param verbose:    Whether to log downloading information. Default: True.

        :raise FileNotFoundError: If the given S3 path do not exist.

        Example:
            >>> s3_client = S3Client()
            >>> s3_client.download(
            ...     bucket="my_bucket",
            ...     local_path="/path/to/a/local/directory",
            ...     s3_path="path/to/a/s3/directory",
            ...     replace=False,
            ... )
        """
        # Initialize a S3 client:
        s3 = self._init_client()

        # Look for all files beginning with the given key (`s3_path`):
        files = self._get_files(s3_client=s3, s3_path=s3_path, bucket=bucket)

        # If the list is empty, there is no such file:
        if len(files) == 0:
            raise FileNotFoundError(
                f"There is no file at the bucket '{bucket}' named '{s3_path}'."
            )

        # Check if it's a single file or directory:
        if len(files) == 1:
            self._download_file(
                s3_client=s3,
                local_path=local_path,
                s3_path=s3_path,
                bucket=bucket,
                replace=replace,
                verbose=verbose,
            )
        else:
            self._download_directory(
                s3_client=s3,
                local_path=local_path,
                s3_directory_path=s3_path,
                s3_files_paths=files,
                bucket=bucket,
                replace=replace,
                verbose=verbose,
            )
        if verbose:
            print("Done!")

    def delete(self, bucket: str, s3_path: str, verbose: bool = True):
        """
        Delete a given file or directory from S3.

        A file is deleted only if the file is not versioned, otherwise this function will just mark it as deleted in its
        latest version.

        :param bucket:  The bucket to delete from.
        :param s3_path: The path to the file or directory to delete in the S3 bucket.
        :param verbose: Whether to log deletion information. Default: True.

        :raise FileNotFoundError: If the given S3 path do not exist.

        Example:
            >>> s3_client = S3Client()
            >>> s3_client.delete(
            ...     bucket="my_bucket",
            ...     s3_path="path/to/a/s3/directory",
            ... )
        """
        # Initialize a S3 client:
        s3 = self._init_client()

        # Look for all files beginning with the given key (`s3_path`):
        files = self._get_files(s3_client=s3, s3_path=s3_path, bucket=bucket)

        # If the list is empty, there is no such file:
        if len(files) == 0:
            raise FileNotFoundError(
                f"There is no file at the bucket '{bucket}' named '{s3_path}'."
            )

        # Check if it's a single file or directory:
        if len(files) == 1:
            self._delete_file(
                s3_client=s3,
                s3_path=s3_path,
                bucket=bucket,
                verbose=verbose,
            )
        else:
            self._delete_directory(
                s3_client=s3,
                s3_files_paths=files,
                bucket=bucket,
                verbose=verbose,
            )
        if verbose:
            print("Done!")

    def _init_client(self):
        return boto3.client(
            service_name="s3",
            aws_access_key_id=self._aws_access_key_id,
            aws_secret_access_key=self._aws_secret_access_key,
        )

    @staticmethod
    def _get_files(s3_client, s3_path: str, bucket: str) -> List[str]:
        return [
            file["Key"]
            for file in s3_client.list_objects(Bucket=bucket, Prefix=s3_path).get(
                "Contents", []
            )
        ]

    @staticmethod
    def _upload_file(
        s3_client,
        local_path: str,
        s3_path: str,
        bucket: str,
        replace: bool,
        verbose: bool,
    ):
        # Check if needed to upload:
        if replace:
            upload = True  # `replace` is set to True:
        else:
            # Look for the file to know if its already exist:
            files = S3Client._get_files(
                s3_client=s3_client, s3_path=s3_path, bucket=bucket
            )
            if files:
                upload = False  # `replace` is set to False as the file was found.
            else:
                upload = True  # The file was not found.

        # Upload only if needed:
        if upload:
            if verbose:
                print(f"Uploading '{local_path}' to {s3_path}")
            s3_client.upload_file(Filename=local_path, Bucket=bucket, Key=s3_path)
        elif verbose:
            print(f"Skipping '{local_path}' as {s3_path} already exist")

    @staticmethod
    def _upload_directory(
        s3_client,
        local_path: str,
        s3_path: str,
        bucket: str,
        replace: bool,
        verbose: bool,
    ):
        # List all files in directory:
        files = [
            path
            for path in glob.iglob(os.path.join(local_path, "**"), recursive=True)
            if os.path.isfile(path)
        ]
        if len(files) == 0:
            raise ValueError(
                f"Found 0 files to upload as the given directory '{local_path}' is empty"
            )

        # Upload the files:
        files_iterator = tqdm(files, desc="Uploading") if verbose else files
        for file in files_iterator:
            if verbose:
                files_iterator.set_postfix({"file": file})
            S3Client._upload_file(
                s3_client=s3_client,
                local_path=file,
                s3_path=os.path.join(s3_path, os.path.relpath(file, local_path)),
                bucket=bucket,
                replace=replace,
                verbose=verbose,
            )

    @staticmethod
    def _download_file(
        s3_client,
        local_path: str,
        s3_path: str,
        bucket: str,
        replace: bool,
        verbose: bool,
    ):
        # Check if needed to download:
        if replace:
            download = True  # `replace` is set to True:
        else:
            # Look for the file to know if its already exist:
            download = not os.path.exists(local_path)

        # Download only if needed:
        if download:
            if verbose:
                print(f"Downloading '{s3_path}' to {local_path}")
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            s3_client.download_file(Filename=local_path, Bucket=bucket, Key=s3_path)
        elif verbose:
            print(f"Skipping '{s3_path}' as {local_path} already exist")

    @staticmethod
    def _download_directory(
        s3_client,
        local_path: str,
        s3_directory_path: str,
        bucket: str,
        s3_files_paths: List[str],
        replace: bool,
        verbose: bool,
    ):
        # Download the files:
        files_iterator = (
            tqdm(s3_files_paths, desc="Downloading") if verbose else s3_files_paths
        )
        for file in files_iterator:
            if verbose:
                files_iterator.set_postfix({"file": file})
            S3Client._download_file(
                s3_client=s3_client,
                local_path=os.path.join(
                    local_path, os.path.relpath(file, s3_directory_path)
                ),
                s3_path=file,
                bucket=bucket,
                replace=replace,
                verbose=verbose,
            )

    @staticmethod
    def _delete_file(
        s3_client,
        s3_path: str,
        bucket: str,
        verbose: bool,
    ):
        # Delete (only if the file is not versioned, otherwise it will just mark it as deleted in its latest version):
        if verbose:
            print(f"Deleting '{s3_path}'")
        s3_client.delete_object(Bucket=bucket, Key=s3_path)

    @staticmethod
    def _delete_directory(
        s3_client,
        s3_files_paths: List[str],
        bucket: str,
        verbose: bool,
    ):
        # Delete the files:
        files_iterator = (
            tqdm(s3_files_paths, desc="Deleting") if verbose else s3_files_paths
        )
        for file in files_iterator:
            if verbose:
                files_iterator.set_postfix({"file": file})
            S3Client._delete_file(
                s3_client=s3_client,
                s3_path=file,
                bucket=bucket,
                verbose=verbose,
            )

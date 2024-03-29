import os, shutil

from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.shortcuts import reverse, HttpResponseRedirect, HttpResponse
from django.core.exceptions import ObjectDoesNotExist

from file_upload.forms import UploadFileForm
from file_upload.models import File, SharedFileWith
from filesonline.utils import (encrypt_file, decrypt_file, find_good_name,
    get_file_type, human_readable_size, get_vault_token, check_vault_token)
from filesonline.settings import DEFAULT_PROFILE_PIC_URL


class RedirectHome(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def get(self, request):
        return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': ''}))


class MainPage(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def get(self, request, path=''):

        upload_form = UploadFileForm()

        files = File.objects.filter(
            owner=request.user,
            path=path,
            hidden=False,
        ).order_by('-is_directory', '-filename')

        directories = files.filter(is_directory=True)

        shared_by_me = request.user.files.filter(shared=True)

        for file in shared_by_me:
            for i in file.instances.all():
                print(i.shared_with)

        shared_with_me = request.user.shared_with.all()

        # print('received:{}'.format(request.session.get('vault')))
        # print()

        vault_access = True
        if not check_vault_token(request.session.get('vault'), request.user):
            vault_access = False
            request.session['vault'] = None


        context = {
            'path': path,
            'files': files,
            'directories': directories,
            'upload_form': upload_form,
            'shared_by_me': shared_by_me,
            'shared_with_me': shared_with_me,
            'vault_access': vault_access,
            'default_profile_pic_url': DEFAULT_PROFILE_PIC_URL,
        }

        return render(request, 'page/my_page.html', context=context)

    def post(self, request, path):

        form = UploadFileForm(request.POST, request.FILES)

        if form.is_valid():

            files = request.FILES.getlist('file')

            def handle_uploaded_file(f, filename):
                with open(filename, 'ab+') as destination:
                    for chunk in f.chunks():
                        destination.write(chunk)

            for f in files:
                handle_uploaded_file(
                    request.FILES['file'],
                    os.path.join(os.path.join(request.user.user_profile.folder, path), f.name)
                )

                try:
                    existing = File.objects.get(owner=request.user, filename=f.name)
                    if existing:
                        existing.delete()
                except ObjectDoesNotExist:
                    pass

                db_file = File()

                db_file.owner = request.user
                db_file.filename = f.name
                db_file.path = path
                db_file.file_type = get_file_type(os.path.splitext(f.name)[1])
                db_file.size = human_readable_size(f.size)

                db_file.save()

        return HttpResponseRedirect(reverse('mypage:main_page', kwargs = {'path': path}))


class VaultPage(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def get(self, request):

        if not check_vault_token(request.session.get('vault'), request.user):
            request.session['vault'] = None

            return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': ''}))

        vault_files = File.objects.filter(
            owner=request.user,
            hidden=True,
        ).order_by('-filename')


        context = {
            'vault_files': vault_files,
            'path': '',
            'default_profile_pic_url': DEFAULT_PROFILE_PIC_URL,
        }

        return render(request, 'page/vault_page.html', context=context)


class DeleteFile(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        file = request.POST.get('file')
        path = request.POST.get('path', '')

        if file:

            db_file = File.objects.get(owner=request.user, filename=file, path=path)

            if db_file.hidden:

                if not check_vault_token(request.session.get('vault'), request.user):
                    return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': ''}))

                os.remove(os.path.join(
                    request.user.user_profile.folder + '_vault',
                    file,
                ))

                db_file.delete()

                return HttpResponseRedirect(reverse('mypage:vault_page'))

            # print(db_file)
            db_file.delete()

            # print(os.path.join(os.path.join(request.user.user_profile.folder, path), file))
            os.remove(os.path.join(os.path.join(request.user.user_profile.folder, path), file))
        # return HttpResponse('<script>history.back();</script>')

        return HttpResponseRedirect(reverse('mypage:main_page', kwargs = {'path': path}))


class DownloadFile(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        file = request.POST.get('file')
        path = request.POST.get('path', '')

        db_file = File.objects.get(owner=request.user, filename=file, path=path)

        if db_file.hidden:

            if not check_vault_token(request.session.get('vault'), request.user):
                return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': ''}))

            file_path = os.path.join(
                request.user.user_profile.folder + '_vault',
                file,
            )

            redirect_rev = reverse('mypage:vault_page')
        else:

            file_path = os.path.join(os.path.join(request.user.user_profile.folder, path), file)
            redirect_rev = reverse('mypage:main_page', kwargs={'path': path})

        if os.path.exists(file_path):
            with open(file_path, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type="application/vnd.ms-excel")
                response['Content-Disposition'] = 'inline; filename=' + os.path.basename(file_path)
                return response

        return HttpResponseRedirect(redirect_rev)


class DecryptDownloadFile(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        file = request.POST.get('file')
        path = request.POST.get('path', '')

        db_file = File.objects.get(owner=request.user, filename=file, path=path)

        if db_file.hidden:
            if not check_vault_token(request.session.get('vault'), request.user):
                return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': ''}))

            file_path = os.path.join(request.user.user_profile.folder + '_vault', file)
        else:
            file_path = os.path.join(os.path.join(request.user.user_profile.folder, path), file)

        if db_file.encrypted is False:
            return DownloadFile().post(request)

        dec_path = decrypt_file(file_path, request.user)

        with open(dec_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/vnd.ms-excel")
            response['Content-Disposition'] = 'inline; filename=' + os.path.basename(dec_path)

        os.remove(dec_path)

        return response


class ShareFile(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        file = request.POST.get('file')
        path = request.POST.get('path', '')
        share_with = request.POST.get('share_with')

        file_obj = File.objects.get(owner=request.user, filename=file, path=path)

        if file_obj.hidden:
            HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': path}))

        file_path = os.path.join(os.path.join(request.user.user_profile.folder, file_obj.path), file)
        share_with_user = User.objects.get(username=share_with)

        if (
                os.path.exists(file_path)
                and share_with_user
                and share_with_user != request.user
        ):
            shared_file = SharedFileWith()

            existing = SharedFileWith.objects.filter(
                shared_with=share_with_user,
                file__filename=file,
                file__owner=request.user,
                file__path=path,
            )

            if not existing:

                file_to_share = File.objects.get(owner=request.user, filename=file, path=path)

                file_to_share.shared = True

                shared_file.file = file_to_share
                shared_file.shared_with = share_with_user

                shared_file.save()
                file_to_share.save()

        return HttpResponseRedirect(reverse('mypage:main_page', kwargs = {'path': path}))


class MoveSharedFile(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        file = request.POST.get('file')
        path = request.POST.get('path', '')

        dest_path = os.path.join(os.path.join(request.user.user_profile.folder, path), file)

        db_file = File()

        db_file.owner = request.user
        db_file.filename = file

        if os.path.exists(dest_path):

            dest_path, i = find_good_name(dest_path)
            base, ext = os.path.splitext(db_file.filename)
            db_file.filename = ''.join([
                base,
                ' ({})'.format(i),
                ext,
            ])

        shared_file_obj = SharedFileWith.objects.get(
                shared_with=request.user,
                file__filename=file
        )


        db_file.file_type = shared_file_obj.file.file_type
        db_file.size = shared_file_obj.file.size

        file_owner = shared_file_obj.file.owner
        file_path = os.path.join(
            os.path.join(file_owner.user_profile.folder, shared_file_obj.file.path),
            file,
        )

        if os.path.exists(file_path):
            shutil.copyfile(file_path, dest_path)
            db_file.path = path


            if shared_file_obj.file.encrypted:
                db_file.encrypted = True

            db_file.save()

        return HttpResponseRedirect(reverse('mypage:main_page', kwargs = {'path': path}))


class EncryptFile(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        file = request.POST.get('file')
        path = request.POST.get('path', '')

        db_file = File.objects.get(owner=request.user, filename=file, path=path)

        if db_file.hidden:
            if not check_vault_token(request.session.get('vault'), request.user):
                return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': ''}))

            file_path = os.path.join(request.user.user_profile.folder + '_vault', file)
            redirect = reverse('mypage:vault_page')
        else:
            file_path = os.path.join(os.path.join(request.user.user_profile.folder, path), file)
            redirect = reverse('mypage:main_page', kwargs = {'path': path})

        if db_file.encrypted is False:

            new_path = encrypt_file(file_path, request.user)

            db_file.filename = os.path.basename(new_path)
            db_file.encrypted = True

            db_file.save()

            os.remove(file_path)

        return HttpResponseRedirect(redirect)


class DecryptFile(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        file = request.POST.get('file')
        path = request.POST.get('path', '')

        db_file = File.objects.get(owner=request.user, filename=file, path=path)

        if db_file.hidden:
            if not check_vault_token(request.session.get('vault'), request.user):
                return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': ''}))

            file_path = os.path.join(request.user.user_profile.folder + '_vault', file)
            redirect = reverse('mypage:vault_page')
        else:
            file_path = os.path.join(os.path.join(request.user.user_profile.folder, path), file)
            redirect = reverse('mypage:main_page', kwargs = {'path': path})

        if db_file.encrypted is True:
            # db_file.filename = db_file.filename[:-4]
            # db_file.encrypted = False
            #
            # decrypt_file(file_path, request.user)

            new_path = decrypt_file(file_path, request.user)

            db_file.filename = os.path.basename(new_path)
            db_file.encrypted = False

            db_file.save()

            os.remove(file_path)

        return HttpResponseRedirect(redirect)


class MakeDirectory(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        dir = request.POST.get('dir')
        path = request.POST.get('path', '')

        dir_obj = File.objects.filter(owner=request.user, filename=dir, path=path, is_directory=True)

        if not dir_obj:
            new_dir = File()

            new_dir.owner = request.user
            new_dir.filename = dir
            new_dir.path = path
            new_dir.is_directory = True

            dir_path = os.path.join(os.path.join(request.user.user_profile.folder, path), dir)

            os.mkdir(dir_path)

            new_dir.save()

        return HttpResponseRedirect(reverse('mypage:main_page', kwargs = {'path': path}))


class ChangeDirectory(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        dir = request.POST.get('dir')
        path = request.POST.get('path', '')

        if not dir:
            return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': path}))

        dir_obj = File.objects.get(owner=request.user, filename=dir, path=path, is_directory=True)

        if dir_obj:

            path = os.path.join(dir_obj.path, dir)


        return HttpResponseRedirect(reverse('mypage:main_page', kwargs = {'path': path}))


class DeleteDirectory(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        dir = request.POST.get('dir')
        path = request.POST.get('path', '')

        if not dir:
            return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': path}))

        dir_obj = File.objects.get(owner=request.user, filename=dir, path=path, is_directory=True)

        if dir_obj:

            shutil.rmtree(os.path.join(os.path.join(request.user.user_profile.folder, path), dir))

            paths_to_delete = [os.path.join(dir_obj.path, dir_obj.filename)]

            user_files = File.objects.filter(owner=request.user)

            while paths_to_delete:

                searched_path = paths_to_delete.pop()

                files = user_files.filter(path=searched_path)

                for file in files:
                    if file.is_directory:
                        paths_to_delete.append(os.path.join(searched_path, file.filename))

                    file.delete()

            dir_obj.delete()

        return HttpResponseRedirect(reverse('mypage:main_page', kwargs = {'path': path}))


class MoveToDirectory(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        file = request.POST.get('file')
        path = request.POST.get('path', '')
        new_dir = request.POST.get('new_dir')

        if not file:
            return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': path}))

        file_obj = File.objects.get(owner=request.user, filename=file, path=path)

        if file_obj:
            old_path = os.path.join(os.path.join(request.user.user_profile.folder, path), file)
            new_path = os.path.join(
                os.path.join(os.path.join(request.user.user_profile.folder, path), new_dir),
                file,
            )

            if os.path.exists(new_path):

                new_path, i = find_good_name(new_path)
                base, ext = os.path.splitext(file_obj.filename)
                file_obj.filename = ''.join([
                    base,
                    ' ({})'.format(i),
                    ext,
                ])

            os.rename(old_path, new_path)

            file_obj.path = os.path.join(file_obj.path, new_dir)

            file_obj.save()

        return HttpResponseRedirect(reverse('mypage:main_page', kwargs = {'path': path}))


class CopyFile(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        file = request.POST.get('file')
        path = request.POST.get('path', '')

        if not file:
            return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': path}))

        file_obj = File.objects.get(owner=request.user, filename=file, path=path)

        if file_obj.hidden:
            if not check_vault_token(request.session.get('vault'), request.user):
                return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': ''}))

            file_path = os.path.join(request.user.user_profile.folder + '_vault', file)
            redirect = reverse('mypage:vault_page')
        else:
            file_path = os.path.join(os.path.join(request.user.user_profile.folder, path), file)
            redirect = reverse('mypage:main_page', kwargs={'path': path})

        if file_obj:
            copy_file_obj = File()

            base_path, ext = os.path.splitext(file_path)
            copy_path = base_path + ' - Copy' + ext


            copy_file_obj.owner = request.user
            copy_file_obj.filename = os.path.splitext(file)[0] + ' - Copy' + ext
            copy_file_obj.path = file_obj.path
            copy_file_obj.file_type = file_obj.file_type
            copy_file_obj.size = file_obj.size
            copy_file_obj.hidden = file_obj.hidden

            if os.path.exists(copy_path):
                copy_path, i = find_good_name(copy_path)
                copy_file_obj.filename = ''.join([
                    os.path.splitext(copy_file_obj.filename)[0],
                    ' ({})'.format(i),
                    ext,
                ])

            shutil.copyfile(file_path, copy_path)

            copy_file_obj.save()

        return HttpResponseRedirect(redirect)


class UnshareFile(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        user_pk = request.POST.get('user')
        file = request.POST.get('file')
        path = request.POST.get('path')

        try:
            file_obj = File.objects.get(owner=request.user, filename=file)
            user_obj = User.objects.get(pk=user_pk)

            obj = SharedFileWith.objects.get(file=file_obj, shared_with=user_obj)
            obj.delete()

            if not file_obj.instances.all():
                file_obj.shared = False
                file_obj.save()

        except ObjectDoesNotExist:
            pass

        return HttpResponseRedirect(reverse('mypage:main_page', kwargs = {'path': path}))


class EnterVaultKey(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        path = request.POST.get('path')
        vault_key = request.POST.get('vault_key')


        if vault_key == request.user.user_profile.vault_key:
            token = get_vault_token(request.user)

            # print('Original:{}'.format(token))

            request.session['vault'] = token

        return HttpResponseRedirect(reverse('mypage:main_page', kwargs = {'path': path}))


class HideFile(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        path = request.POST.get('path')
        file = request.POST.get('file')

        if (
                check_vault_token(request.session.get('vault'), request.user)
        ):
            file_obj = File.objects.get(owner=request.user, filename=file, path=path)

            file_path = os.path.join(
                os.path.join(request.user.user_profile.folder, file_obj.path),
                file_obj.filename,
            )

            new_file_path = os.path.join(
                request.user.user_profile.folder + '_vault',
                file_obj.filename,
            )

            shutil.copyfile(file_path, new_file_path)

            file_obj.path = ''
            file_obj.hidden = True

            if file_obj.shared:
                file_obj.shared = False
                for instance in file_obj.instances.all():
                    instance.delete()

            file_obj.save()

            os.remove(file_path)

        return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': path}))


class UnhideFile(LoginRequiredMixin, View):

    login_url = '/user/login/'
    redirect_field_name = 'index.html'

    def post(self, request):

        path = request.POST.get('path')
        file = request.POST.get('file')

        if (
                check_vault_token(request.session.get('vault'), request.user)
        ):
            file_obj = File.objects.get(owner=request.user, filename=file, path=path)

            if not file_obj.hidden:
                return HttpResponseRedirect(reverse('mypage:main_page', kwargs={'path': path}))

            new_file_path = os.path.join(
                request.user.user_profile.folder,
                file_obj.filename,
            )

            file_path = os.path.join(
                request.user.user_profile.folder + '_vault',
                file_obj.filename,
            )

            shutil.copyfile(file_path, new_file_path)

            file_obj.path = ''
            file_obj.hidden = False

            file_obj.save()

            os.remove(file_path)

        return HttpResponseRedirect(reverse('mypage:vault_page'))

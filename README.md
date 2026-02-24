# YAML-based Team Management

Control organization teams from a single `teams.yaml` file. 

# Workflow 

* Changes to `team.yaml` on the `main` branch triggers workflow run. YAML becomes the ground truth, GitHub settings mirror it. 

* Manual changes to the settings are checked on an hourly basis. If there is a difference, a PR is created. 

# Setup
To set up, an OWNER of the _organization_ must give the adequate access levels to an GitHub App and set up the repository secrets. 

After tokens are set, anyone with ADMIN/WRITE access to the _repository_ will be able to change teams and invite people to the org. 

## 1. Copy the Template Repository

1. Click the "Use this template" button at the top of this repository (or fork it)

## 2. Set up tokens via a personal GitHub App

The workflows require a GitHub App to authenticate and manage teams on behalf of your organization without giving it an owners' Personal Access Token (PAT). This is [a standard workflow](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow) for these kind of permissions. 

1. Go to your organization settings > Developer settings (on the very bottom > GitHub Apps (the URL will be: `https://github.com/organizations/YOUR_ORG/settings/apps` - replace `YOUR_ORG` with your organization name)

<img width="345" height="353" alt="grafik" src="https://github.com/user-attachments/assets/680e78a2-fc4f-4bf4-a7ae-aeff63dd1794" />

3. Click **"New GitHub App"**

<img width="863" height="275" alt="grafik" src="https://github.com/user-attachments/assets/24754398-ec5b-4452-baad-79ec4a66875f" />

5. Configure the app with these settings:
   - **GitHub App name**: Choose a name (e.g., "Team Management Bot")
   - **Homepage URL**: Use your repository URL, e.g. https://github.com/yaml-team-management/management, but that does not affect behaviour
  
Leave everything as default until you get to:
   - **Webhook**: Uncheck "Active" (not needed)

Then configure the permissions
   - **Permissions** (Repository permissions):
     - Contents: Read and write
     - Pull requests: Read and write
   - **Permissions** (Organization permissions):
     - Administration: Read (to list teams)
     - Members: Read and write
   - **Where can this GitHub App be installed?**: Only on this account
6. Click **"Create GitHub App"**
<img width="557" height="203" alt="grafik" src="https://github.com/user-attachments/assets/4e0330b7-a8a0-4e18-82fd-5e735db79bc8" />

You will get to a page like: 

<img width="1221" height="279" alt="grafik" src="https://github.com/user-attachments/assets/cb2dbc3f-d065-4ae9-b6fd-353e334cebc6" />

On the left bar, click on "Install App" install the GitHub App for your organization: 

<img width="907" height="237" alt="grafik" src="https://github.com/user-attachments/assets/9d5f36ed-f294-4a57-8271-3c0fa6a21e35" />

The [better practice](https://en.wikipedia.org/wiki/Principle_of_least_privilege) is installing  the app only for the cloned `management` repository: 

<img width="583" height="735" alt="grafik" src="https://github.com/user-attachments/assets/9960c744-41dc-46cd-8a76-91f955526c4c" />


Don't close this tab: you will need it for step 3. 


## 3. Configure Repository Secrets

Add the GitHub App credentials as repository secrets:

1. Go to the repository you cloned  

2. Go to settings > Secrets and variables > Actions > Repository secrets (the URL will be: `https://github.com/YOUR_ORG/management/settings/secrets/actions` - replace with your org and repo names)

<img width="1024" height="331" alt="grafik" src="https://github.com/user-attachments/assets/4a6459bb-9c60-4993-b63e-280473a4ae97" />

2. Click **"New repository secret"** and add:
   - **Name**: `GH_APP_ID`
   - **Value**: Your GitHub App ID. It is a number with 7 digits on the "About" page of your app, e.g.:
<img width="331" height="135" alt="grafik" src="https://github.com/user-attachments/assets/9a729537-0f11-41f3-b83c-f105b1b7e29d" />

<img width="706" height="529" alt="grafik" src="https://github.com/user-attachments/assets/65146b23-b405-471f-ba01-d209e968ec3a" />

3. Now, on the App settings page (something like `https://github.com/organizations/YOUR_ORG/settings/apps/team-management-bot`) click on "Generate a Private Key". This will generate and download a key into a `.pem` file: 

<img width="542" height="117" alt="grafik" src="https://github.com/user-attachments/assets/110baae1-3e40-47f6-8746-691ad1035b0a" />


4. Go back to the repository **"New repository secret"** again and add:
   - **Name**: `GH_APP_PRIVATE_KEY`
   - **Value**: Copy and paste the entire contents of the `.pem` file (including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----` lines)

Now your repository secrets are set and the workflows will have the authorization to run: 

<img width="691" height="239" alt="grafik" src="https://github.com/user-attachments/assets/536367aa-bcce-4bff-8d9a-55885f0d6587" />

## Export Your Current Team Structure

Once you have set up the system, manually trigger the **"GitHub → YAML"** workflow to export your current team structure:
   - Go to the **Actions** tab in your repository
   - Select and run the **"GitHub settings → teams.yaml sync"** workflow from the left sidebar

(see the "Features" session to see what this framework can or not do)

## Usage

Once set up, the repository will:

- **Automatically export** team changes made in GitHub UI (runs hourly via cron)
- **Automatically apply** changes when you merge PRs that modify `teams.yaml`

It is good to protect the `main` branch and only allow changes to `teams.yaml` via a Pull Request + merge workflow, but any changes to the file will trigger the new settings in the org. 

Make sure you trust anyone with _repository_ write permissions to modify the teams in the organization and invite new people. 

## Troubleshooting

If you have some trouble using the workflow, please report it at the [GitHub issue tracker](https://github.com/codigobonito/management).

### Scheduled Workflow Delays

The hourly sync workflow uses GitHub Actions' `schedule` trigger. Note that:

- **Scheduled runs are not guaranteed to execute at exact times.** Delays of 10-30 minutes are normal, especially during periods of high GitHub Actions load.
- **During peak load, scheduled runs may be dropped entirely** without appearing in the Actions log.
- The schedule is staggered to 33 minutes past the hour to reduce queue congestion.
- If you notice missing scheduled runs, you can always trigger the workflow manually via the "Run workflow" button in the Actions tab.

For more details, see [GitHub's documentation on scheduled workflows](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule). 
# Features

## Implemented 

* Include/exclude people from teams that exist (even if the people are not in the org)
* Manage invites for non-org members and auto team inclusion (when sync is run)
* Validate GitHub usernames in pull requests before merging
* **Repository Permissions Visibility**: Display write-level (and above) permissions for tracked repositories in `repos.yaml` (read-only mode)

## **Not** implemented 

Some might be implemented if (1) there is a need and (2) they are secure: 

* Create/Remove teams
* Remove people from the organization
* Change permissions of individual people or teams
* Handle team nesting

# Notes

* Users not in the org will be assigned to a list. After they accept the invitation, they will be added to the correct teams on the hourly sync workflow. 
* Teams not listed in the YAML file will be simply ignored (not deleted nor emptied)

# Repository Permissions Visibility

This feature provides a read-only view of write-level (and above) permissions for selected repositories.

## What it does

The system can export repository permissions from GitHub to a `repos.yaml` file, making it easy to:
- **Audit permissions**: See all write, maintain, and admin access in one place
- **Track changes**: Version control repository access using git
- **Improve transparency**: Make repository permissions visible to the team

## How to use

1. **Add repositories to track**: Edit `repos.yaml` and add repository names to the `tracked_repos` list:

```yaml
tracked_repos:
  - team-management
  - my-repo
  - another-repo
```

2. **Run the sync workflow**: Go to Actions → "GitHub repos permissions → repos.yaml sync" and click "Run workflow"

3. **Review the output**: The workflow will create a PR with updated permissions in `repos.yaml`

## What it tracks

The feature exports:
- **Admin** permissions (teams and individual users)
- **Maintain** permissions (teams and individual users)  
- **Write** permissions (teams and individual users)
- **Triage** permissions (teams and individual users)

**Read-only permissions are NOT tracked** as they don't allow modifications to the repository.

## Important notes

- **Read-only mode**: This feature only displays permissions. It does NOT manage or change permissions.
- **Manual trigger only**: The workflow runs only when manually triggered via workflow_dispatch. It does not run automatically.
- **Tracked repos only**: Only repositories listed in `tracked_repos` are scanned.

## Use cases

1. **Security audits**: Quickly review who has write access to critical repositories
2. **Onboarding**: Help new team members understand repository access structure
3. **Access verification**: Confirm that team members have appropriate permissions
4. **Change tracking**: Use git history to track when permissions were modified in GitHub

# Development

## Running Tests

See [tests/README.md](tests/README.md) for more details on the test suite.

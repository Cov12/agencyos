<script lang="ts">
	let orgName = 'AgencyOS Global';
	let domain = 'agencyos.ai/global';

	const team = [
		{ initials: 'SA', name: 'Sarah Anders', email: 'sarah@agencyos.ai', role: 'OWNER', roleStyle: 'bg-[#6961ff]/10 text-[#6961ff] border-[#6961ff]/20', lastActive: 'Just now', gradient: true },
		{ initials: '', name: 'Julian Chen', email: 'jchen@agencyos.ai', role: 'ADMIN', roleStyle: 'bg-slate-100/10 text-slate-100 border-white/10', lastActive: '2 hours ago' },
		{ initials: 'MM', name: 'Marco Mendez', email: 'marco@agencyos.ai', role: 'MEMBER', roleStyle: 'bg-[#20B2AA]/10 text-[#20B2AA] border-[#20B2AA]/20', lastActive: 'Yesterday' },
	];

	const integrations = [
		{ name: 'Discord', desc: 'Community & Bot Hub', enabled: true, bg: 'bg-[#5865F2]/10' },
		{ name: 'Notion', desc: 'Knowledge Base Sync', enabled: true, bg: 'bg-black' },
		{ name: 'GitHub', desc: 'Codebase Automation', enabled: false, bg: 'bg-[#24292E]/20' },
	];
</script>

<div class="w-full h-full overflow-y-auto px-4 py-6 sm:px-6 sm:py-8 lg:p-12">
	<div class="max-w-5xl mx-auto">
		<!-- Header -->
		<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 sm:gap-6 mb-8 lg:mb-12">
			<div>
				<h2 class="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-100 tracking-tight">Organization Settings</h2>
				<p class="text-sm sm:text-base text-slate-400 mt-1.5 sm:mt-2">Manage your workspace members, permissions, and configuration.</p>
			</div>
			<div class="flex flex-col sm:flex-row gap-2 sm:gap-3">
				<button class="flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 text-slate-100 px-4 sm:px-5 py-2.5 rounded-lg border border-white/10 font-semibold transition-all text-sm">
					<span class="material-symbols-outlined text-[20px]">file_download</span>
					Export Audit Logs
				</button>
				<button class="flex items-center justify-center gap-2 bg-[#6961ff] hover:bg-[#6961ff]/90 text-white px-4 sm:px-5 py-2.5 rounded-lg font-bold shadow-lg shadow-[#6961ff]/20 transition-all text-sm">
					<span class="material-symbols-outlined text-[20px]">person_add</span>
					Invite Member
				</button>
			</div>
		</div>

		<div class="grid grid-cols-1 gap-6 lg:gap-8">
			<!-- Workspace Details -->
			<section class="glass rounded-xl p-5 sm:p-6 lg:p-8">
				<div class="flex items-center gap-2 mb-6 lg:mb-8">
					<span class="material-symbols-outlined text-[#6961ff]">edit_square</span>
					<h3 class="text-base lg:text-lg font-bold text-slate-100">Workspace Details</h3>
				</div>
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-5 sm:gap-6 lg:gap-8">
					<div class="space-y-2">
						<label class="text-sm font-semibold text-slate-400 px-1">Organization Name</label>
						<input bind:value={orgName} class="w-full bg-[#1c1c21] border border-white/10 rounded-lg px-4 py-3 text-slate-100 focus:ring-2 focus:ring-[#6961ff] focus:border-transparent transition-all outline-none text-sm" />
					</div>
					<div class="space-y-2">
						<label class="text-sm font-semibold text-slate-400 px-1">Workspace Domain</label>
						<input bind:value={domain} class="w-full bg-[#1c1c21] border border-white/10 rounded-lg px-4 py-3 text-slate-100 focus:ring-2 focus:ring-[#6961ff] focus:border-transparent transition-all outline-none text-sm" />
					</div>
				</div>
			</section>

			<!-- Team -->
			<section class="glass rounded-xl overflow-hidden">
				<div class="p-5 sm:p-6 lg:p-8 pb-3 sm:pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
					<div class="flex items-center gap-2">
						<span class="material-symbols-outlined text-[#20B2AA]">groups</span>
						<h3 class="text-base lg:text-lg font-bold text-slate-100">Team Members</h3>
					</div>
					<span class="bg-[#20B2AA]/10 text-[#20B2AA] text-[10px] font-bold px-2 py-1 rounded tracking-wider uppercase w-fit">12 Active Seats</span>
				</div>
				<div class="overflow-x-auto">
					<table class="w-full text-left">
						<thead>
							<tr class="border-b border-white/5 text-slate-500 text-xs font-semibold uppercase tracking-wider">
								<th class="px-5 sm:px-8 py-4">User</th>
								<th class="px-5 sm:px-8 py-4">Role</th>
								<th class="px-5 sm:px-8 py-4">Last Active</th>
								<th class="px-5 sm:px-8 py-4 text-right">Actions</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-white/5">
							{#each team as member}
								<tr class="hover:bg-white/5 transition-colors">
									<td class="px-5 sm:px-8 py-3 sm:py-4">
										<div class="flex items-center gap-3">
											<div class="size-9 rounded-full {member.gradient ? 'bg-gradient-to-tr from-[#6961ff] to-[#20B2AA]' : 'bg-slate-700'} flex items-center justify-center font-bold text-xs text-white shrink-0">
												{member.initials || member.name.charAt(0)}
											</div>
											<div class="min-w-0">
												<p class="text-sm font-semibold text-slate-100 truncate">{member.name}</p>
												<p class="text-xs text-slate-500 truncate">{member.email}</p>
											</div>
										</div>
									</td>
									<td class="px-5 sm:px-8 py-3 sm:py-4">
										<span class="px-2.5 py-1 rounded-full text-[11px] font-bold {member.roleStyle} border">{member.role}</span>
									</td>
									<td class="px-5 sm:px-8 py-3 sm:py-4 text-sm text-slate-400 font-medium">{member.lastActive}</td>
									<td class="px-5 sm:px-8 py-3 sm:py-4 text-right">
										<button class="material-symbols-outlined text-slate-500 hover:text-white transition-colors">more_horiz</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</section>

			<!-- Billing -->
			<div class="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
				<div class="lg:col-span-1 glass rounded-xl p-5 sm:p-6 lg:p-8 relative overflow-hidden">
					<div class="absolute -top-12 -right-12 size-40 bg-[#6961ff]/10 blur-[60px] rounded-full"></div>
					<div class="relative z-10">
						<div class="flex justify-between items-start mb-4 lg:mb-6">
							<span class="text-xs font-bold uppercase tracking-widest text-[#6961ff]">Current Plan</span>
							<span class="material-symbols-outlined text-[#6961ff]">verified</span>
						</div>
						<h4 class="text-2xl sm:text-3xl font-black text-slate-100 tracking-tight">Enterprise Plus</h4>
						<p class="text-slate-400 mt-2 text-sm leading-relaxed">Scale without limits with dedicated AI models and priority support.</p>
						<div class="mt-6 lg:mt-8">
							<div class="text-slate-100 font-bold">$2,499<span class="text-slate-500 text-sm font-normal">/month</span></div>
						</div>
						<button class="w-full mt-4 lg:mt-6 bg-white/10 hover:bg-white/15 text-white py-3 rounded-lg font-bold border border-white/10 transition-all">
							Upgrade Plan
						</button>
					</div>
				</div>

				<div class="lg:col-span-2 glass rounded-xl p-5 sm:p-6 lg:p-8">
					<div class="flex items-center gap-2 mb-6 lg:mb-8">
						<span class="material-symbols-outlined text-[#6961ff]">analytics</span>
						<h3 class="text-base lg:text-lg font-bold text-slate-100">Monthly Usage</h3>
					</div>
					<div class="space-y-6 lg:space-y-8">
						<div class="space-y-3">
							<div class="flex justify-between items-end">
								<span class="text-sm font-semibold text-slate-100">AI Tokens Processed</span>
								<span class="text-xs font-medium text-slate-400">8.4M / 10M</span>
							</div>
							<div class="w-full h-3 bg-white/5 rounded-full overflow-hidden">
								<div class="h-full bg-gradient-to-r from-[#6961ff] to-[#20B2AA] rounded-full" style="width: 84%"></div>
							</div>
							<p class="text-[11px] text-slate-500 italic">Resetting in 14 days</p>
						</div>
						<div class="space-y-3">
							<div class="flex justify-between items-end">
								<span class="text-sm font-semibold text-slate-100">Automated Workflows</span>
								<span class="text-xs font-medium text-slate-400">42,100 / Unlimited</span>
							</div>
							<div class="w-full h-3 bg-white/5 rounded-full overflow-hidden">
								<div class="h-full bg-[#20B2AA] rounded-full" style="width: 25%"></div>
							</div>
						</div>
					</div>
				</div>
			</div>

			<!-- Integrations -->
			<section class="glass rounded-xl p-5 sm:p-6 lg:p-8">
				<div class="flex items-center justify-between mb-6 lg:mb-8">
					<div class="flex items-center gap-2">
						<span class="material-symbols-outlined text-[#6961ff]">grid_view</span>
						<h3 class="text-base lg:text-lg font-bold text-slate-100">Connected Services</h3>
					</div>
					<a class="text-sm font-semibold text-[#6961ff] hover:underline" href="#">Marketplace</a>
				</div>
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5 lg:gap-6">
					{#each integrations as integ}
						<div class="bg-[#1c1c21]/50 border border-white/10 p-4 sm:p-5 rounded-xl flex items-center gap-4 hover:border-[#6961ff]/30 transition-all {integ.enabled ? '' : 'opacity-70'}">
							<div class="size-10 sm:size-12 rounded-lg {integ.bg} flex items-center justify-center shrink-0">
								<span class="material-symbols-outlined text-white">{integ.name === 'Discord' ? 'forum' : integ.name === 'Notion' ? 'note' : 'code'}</span>
							</div>
							<div class="flex-1 min-w-0">
								<h5 class="text-sm font-bold text-slate-100">{integ.name}</h5>
								<p class="text-[11px] text-slate-500">{integ.desc}</p>
							</div>
							<label class="relative inline-flex items-center cursor-pointer shrink-0">
								<input type="checkbox" checked={integ.enabled} class="sr-only peer" />
								<div class="w-11 h-6 bg-white/10 rounded-full transition-all peer peer-checked:bg-[#6961ff]"></div>
								<div class="absolute left-1 top-1 bg-slate-300 size-4 rounded-full transition-all peer-checked:translate-x-5 peer-checked:bg-white"></div>
							</label>
						</div>
					{/each}
				</div>
			</section>
		</div>
	</div>
</div>

<style>
	.glass {
		background: rgba(28, 28, 33, 0.7);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		border: 1px solid rgba(255, 255, 255, 0.08);
	}
	/* Note: glass class kept as scoped style since it's used on multiple elements
	   and doesn't need dynamic values. Will migrate to GlassPanel when
	   these sections become separate components. */
</style>
